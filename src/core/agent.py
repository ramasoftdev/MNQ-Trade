"""
MNQ Trading Agent v2 — Main Entry Point
=========================================
No webhook server. The agent self-triggers:
  - Tradovate streams 4 bar series (1h, 30m, 15m, 5m)
  - When a 15m or 5m bar closes, sweep detection runs automatically
  - If a sweep is found AND 3+ TFs align, Claude is called and Discord fires

RUN:
  python agent.py

HEALTH CHECK:
  The agent prints a status line every 60 seconds.
"""

import logging
import time
from datetime import datetime, timedelta
import pytz

from src.data.config import (
    ALERT_COOLDOWN_SECS, TIMEZONE, TRIGGER_TIMEFRAMES, MIN_TF_ALIGNMENT,
    SPY_PIVOT_DIRECTION_BONUS,
)
from src.data.data_fetcher import MultiTimeframeFetcher
from src.data.spy_fetcher import SpyFetcher
from src.analysis.context_analyzer import build_mtf_context
from src.analysis.probability_engine import get_probability
from src.reporting.discord_formatter import send_to_discord, send_error_alert, send_tp_sl_alert
from src.levels.spy_levels_analyzer import analyze_spy_levels, get_pivot_direction_bonus, format_spy_score_detail
from src.levels.levels_analyzer import parse_levels_from_file
from src.trading.trade_journal import TradeJournal
from src.reporting.report_scheduler import check_and_send_report

# MVC Imports
from src.controllers.alert_controller import AlertController
from src.database.alert_db import AlertDatabase
from src.views.discord_view import DiscordView

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("agent")
TZ  = pytz.timezone(TIMEZONE)

# ── Global state ──────────────────────────────────────────
fetcher     = MultiTimeframeFetcher()
spy_fetcher = SpyFetcher()
journal     = TradeJournal()    # Trade journal for alert logging (kept for compatibility)

# MVC Components
alert_db    = AlertDatabase()
alert_ctrl  = AlertController(alert_db)
discord_view = DiscordView()

_last_alert: dict = {}     # {direction: datetime} — cooldown tracker


# ── Cooldown helper ───────────────────────────────────────
def _is_cooled_down(direction: str) -> bool:
    last = _last_alert.get(direction)
    if last is None:
        return True
    return (datetime.now(TZ) - last).total_seconds() >= ALERT_COOLDOWN_SECS


def _record_alert(direction: str):
    _last_alert[direction] = datetime.now(TZ)


# ── Historical Context (Option A + B) ──────────────────────
def _get_score_band(confluence_score: float) -> str:
    """Determine score band for a confluence score."""
    if confluence_score >= 10:
        return "10+"
    elif confluence_score >= 8:
        return "8-10"
    elif confluence_score >= 5:
        return "5-8"
    else:
        return "<5"


def _should_alert_on_sweep(confluence_score: float, direction: str) -> bool:
    """
    Check if we should alert based on historical performance (Option B pre-filter).

    Returns False if score band has proven to be unprofitable.
    """
    # Get last 2 weeks of historical data
    stats = journal.get_historical_stats(days=14)

    # Get score band
    band = _get_score_band(confluence_score)
    band_stats = stats["by_score_band"].get(band, {})

    # If no data yet, allow alert
    if not band_stats or band_stats.get("total", 0) == 0:
        log.debug(f"No historical data for band {band}, allowing alert")
        return True

    tp_rate = band_stats.get("tp_rate", 0)

    # Pre-filter rules (Option B)
    if tp_rate == 0:
        log.warning(
            f"Alert skipped: Score band {band} has 0% TP hit rate in last 14 days. "
            f"Not worth trading."
        )
        return False

    if tp_rate < 25:
        log.warning(
            f"Alert skipped: Score band {band} has {tp_rate:.1f}% TP hit rate in last 14 days. "
            f"Too risky to alert."
        )
        return False

    if tp_rate < 40:
        log.info(
            f"Alert allowed but weak: Score band {band} has {tp_rate:.1f}% TP hit rate. "
            f"Proceed cautiously."
        )

    return True


def _build_historical_context(confluence_score: float, direction: str) -> str:
    """
    Build historical context string for Claude (Option A).

    Includes performance data from last 14 days to help Claude calibrate probability.
    """
    stats = journal.get_historical_stats(days=14)

    if stats["overall"]["total_trades"] == 0:
        return (
            "\nHISTORICAL PERFORMANCE: No trades recorded yet. "
            "This is the first assessment period."
        )

    band = _get_score_band(confluence_score)
    band_stats = stats["by_score_band"].get(band, {})
    dir_stats = stats["by_direction"].get(direction, {})
    overall = stats["overall"]

    context = f"""
HISTORICAL PERFORMANCE (Last 14 days):

Score Band {band}:
  Total alerts: {band_stats.get('total', 0)}
  Hit TP: {band_stats.get('tp_hit', 0)} ({band_stats.get('tp_rate', 0):.1f}%)
  Hit SL: {band_stats.get('sl_hit', 0)}

Direction {direction}:
  Total trades: {dir_stats.get('total', 0)}
  Wins: {dir_stats.get('wins', 0)} ({dir_stats.get('win_rate', 0):.1f}%)

Overall (last 14 days):
  Total trades: {overall['total_trades']}
  Win rate: {overall['win_rate']:.1f}%
  Total P&L: ${overall['total_pnl']:.2f}
  Avg P&L per trade: ${overall['avg_pnl']:.2f}

GUIDANCE FOR THIS ALERT:
- If score band {band} historically hits TP {band_stats.get('tp_rate', 0):.0f}%+, be confident
- If direction {direction} has {dir_stats.get('win_rate', 0):.0f}%+ win rate, favor it
- Factor this historical context into your probability assessment"""

    return context


# ── Bar-close callback (called by data_fetcher on 15m/5m close) ──
def on_bar_close(tf: str, bars: list):
    """
    Runs in a background thread each time a 15m or 5m bar closes.
    Pulls all TF bars, checks for a sweep, verifies alignment, fires pipeline.
    """
    log.info(f"Bar closed on {tf} ({len(bars)} bars in buffer)")

    # Get all TF buffers
    mtf_bars = fetcher.get_all_bars()

    # Need a minimum of data on all TFs before analysing
    if not fetcher.is_ready(min_bars=20):
        log.debug("Data buffers not yet full — skipping.")
        return

    # Build MTF context (includes sweep detection + alignment check)
    ctx = build_mtf_context(mtf_bars, trigger_tf=tf)

    if not ctx:
        log.debug(f"No sweep detected on {tf}.")
        return

    # Alignment filter applied inside build_mtf_context
    if ctx.get("insufficient_alignment"):
        alignment = ctx["alignment"]
        sweep     = ctx["sweep"]
        log.info(
            f"Sweep found on {tf} ({sweep['direction'].upper()}) "
            f"but only {alignment['aligned']}/{alignment['total']} TFs aligned "
            f"(need {MIN_TF_ALIGNMENT}) — skipping."
        )
        return

    direction = ctx["direction"]

    # Cooldown check
    if not _is_cooled_down(direction):
        log.info(f"Alert cooldown active for {direction} — skipping duplicate.")
        return

    # ── HISTORICAL PRE-FILTER (Option B) ──────────────────────
    # Check if this score band has proven unprofitable
    if not _should_alert_on_sweep(ctx.get("confluence_score", 0), direction):
        log.info("Alert filtered out by historical pre-filter.")
        return

    # ── SPY MAGNET ANALYSIS ──────────────────────────────────
    spy_price = spy_fetcher.get_price()

    # Parse daily levels to get pivot
    try:
        daily_levels = parse_levels_from_file()
        levels_config = daily_levels.get('spy', {})
    except Exception as e:
        log.warning(f"Could not load daily levels: {e}")
        levels_config = {}

    # Analyze SPY position relative to pivot (magnet logic)
    spy_analysis = analyze_spy_levels(spy_price, levels_config)

    # Direction bonus: +0.5 if sweep aligns with SPY position vs pivot
    direction_bonus = get_pivot_direction_bonus(direction, spy_analysis['pivot_direction'])
    spy_total_score = spy_analysis['total_spy_score'] + direction_bonus

    log.info(f"  SPY magnet: {spy_analysis['analysis']}")
    log.info(f"  SPY score: {format_spy_score_detail(spy_analysis, direction_bonus)}")

    # Add SPY score to context (will be used in confluence scoring)
    ctx['spy_analysis'] = spy_analysis
    ctx['spy_direction_bonus'] = direction_bonus
    ctx['spy_total_score'] = spy_total_score

    # Update overall confluence score
    ctx['confluence_score'] = ctx.get('confluence_score', 0) + spy_total_score

    log.info(
        f"SWEEP on {tf}: {direction.upper()} @ {ctx['current_price']:.2f} "
        f"| alignment {ctx['alignment']['aligned']}/{ctx['alignment']['total']} "
        f"| score {ctx['confluence_score']:.1f} (core + SPY magnet)"
    )

    # ── HISTORICAL CONTEXT (Option A) ──────────────────────────
    # Add historical performance data to context for Claude
    historical_context = _build_historical_context(ctx.get('confluence_score', 0), direction)
    ctx['historical_context'] = historical_context
    log.info(f"Added historical context to alert")

    # Get Claude probability
    try:
        prob = get_probability(ctx)
    except Exception as e:
        log.error(f"Probability engine error: {e}")
        from src.analysis.probability_engine import _fallback_assessment
        prob = _fallback_assessment(str(e))

    log.info(
        f"Claude: {prob.get('probability','?')}% — "
        f"{prob.get('assessment','?')} ({prob.get('confidence','?')} confidence)"
    )

    # Send to Discord
    success = send_to_discord(ctx, prob)
    if success:
        _record_alert(direction)

        # Create and save alert using MVC
        try:
            alert = alert_ctrl.create_alert({
                "timestamp": datetime.now(TZ),
                "direction": direction,
                "current_price": ctx.get("current_price", 0),
                "trigger_tf": ctx.get("trigger_tf", "?"),
                "confluence_score": ctx.get("confluence_score", 0),
                "base_score": ctx.get("base_score", 0),
                "ext_score": ctx.get("ext_score", 0),
                "spy_total_score": ctx.get("spy_total_score", 0),
                "conditions": ctx.get("conditions", {}),
                "vwap": ctx.get("vwap", 0),
                "poc_primary": ctx.get("poc_primary", 0),
                "spy_price": spy_price,
                "probability": prob.get("probability"),
                "assessment": prob.get("assessment"),
                "confidence": prob.get("confidence"),
                "reasoning": prob.get("reasoning", ""),
                "stop_loss": ctx.get("sl_estimate", 0),
                "take_profit": ctx.get("tp_estimate", 0),
            })
            log.info(f"Alert created via MVC: {alert}")
        except Exception as e:
            log.error(f"Failed to create alert via MVC: {e}")

        log.info("Pipeline complete — Discord alert sent.")
    else:
        log.error("Pipeline complete — Discord send failed.")


# ── Market Close Monitor (3:15 PM CT) ──────────────────────
def market_close_monitor_loop():
    """
    Monitor for market close (3:15 PM CT).
    Automatically close any pending alerts at market close with actual exit price.
    """
    _market_close_processed = False  # Track if we've already processed market close today

    while True:
        try:
            now = datetime.now(TZ)
            current_hour = now.hour
            current_minute = now.minute

            # Check if it's 3:15 PM CT or later (15:15 in 24h format)
            is_market_close_time = (current_hour == 15 and current_minute >= 15) or current_hour > 15

            # Only process once per day
            if is_market_close_time and not _market_close_processed:
                log.info("Market close detected (3:15 PM CT) — processing pending alerts...")

                current_price = fetcher.get_latest_price()
                if not current_price:
                    log.warning("Could not get current price for market close processing")
                    time.sleep(60)
                    continue

                # Get all pending alerts from today
                today_str = now.strftime("%Y-%m-%d")
                pending_alerts = journal.get_alerts_by_date(today_str)

                for alert in pending_alerts:
                    if isinstance(alert, dict):
                        alert_id = alert.get("id")
                        exit_type = alert.get("exit_type", "")
                        entry_price = alert.get("current_price", 0)
                        direction = alert.get("direction", "")
                    else:
                        alert_id = alert[0] if len(alert) > 0 else None
                        exit_type = alert[12] if len(alert) > 12 else ""
                        entry_price = alert[5] if len(alert) > 5 else 0
                        direction = alert[2] if len(alert) > 2 else ""

                    # Only process if still pending (no TP/SL hit yet)
                    if alert_id and not exit_type:
                        # Calculate P&L
                        if direction.upper() == "LONG":
                            pnl = current_price - entry_price
                        else:  # SHORT
                            pnl = entry_price - current_price

                        # Mark as market close exit in journal
                        log.info(
                            f"Market close: Alert #{alert_id} ({direction}) "
                            f"entry={entry_price:.2f}, exit={current_price:.2f}, P&L={pnl:.2f}"
                        )

                        # Record market close exit in journal
                        journal.record_market_close_exit(alert_id, current_price)

                _market_close_processed = True
                log.info(f"Market close processing complete. {len(pending_alerts)} alerts checked.")

            # Reset flag at end of day (after 4 PM CT)
            if current_hour >= 16:
                _market_close_processed = False

            time.sleep(60)  # Check every minute

        except Exception as e:
            log.error(f"Market close monitor error: {e}")
            time.sleep(60)


# ── TP/SL Monitor ─────────────────────────────────────────
def tp_sl_monitor_loop():
    """Monitor all open alerts for SL/TP hits and auto-record fills."""
    while True:
        try:
            time.sleep(5)  # Check every 5 seconds

            # Get current price
            current_price = fetcher.get_latest_price()
            if not current_price:
                continue

            # Get all open alerts to monitor
            open_alerts = journal.get_open_alerts_for_monitoring()

            for alert in open_alerts:
                alert_id = alert["id"]
                direction = alert["direction"]
                entry_price = alert["entry_price"]
                sl = alert["stop_loss"]
                tp = alert["take_profit"]
                taken = alert["taken"]

                # Check if price hit SL or TP
                hit_type, hit_price = journal.check_and_record_tp_sl_hit(alert_id, current_price)

                if hit_type:
                    # Send Discord notification
                    try:
                        send_tp_sl_alert(
                            alert_id=alert_id,
                            hit_type=hit_type,
                            direction=direction,
                            entry=entry_price,
                            current=current_price,
                            sl=sl,
                            tp=tp,
                            confidence=alert['confluence_score'],
                            taken=taken
                        )
                    except Exception as e:
                        log.error(f"Failed to send TP/SL notification for alert {alert_id}: {e}")

        except Exception as e:
            log.error(f"TP/SL monitor error: {e}")
            time.sleep(5)


# ── Status printer ────────────────────────────────────────
def status_loop():
    """Prints a brief status line every 60 seconds and checks for daily report."""
    while True:
        time.sleep(60)
        mnq_price = fetcher.get_latest_price()
        spy_price = spy_fetcher.get_price()
        bars  = {tf: len(fetcher.get_bars(tf)) for tf in ["1h","30m","15m","5m"]}
        log.info(
            f"STATUS  MNQ={mnq_price:.2f}  SPY={spy_price:.2f}  "
            f"bars 1h={bars['1h']} 30m={bars['30m']} "
            f"15m={bars['15m']} 5m={bars['5m']}  "
            f"MNQ_connected={fetcher.connected}  SPY_connected={spy_fetcher.connected}"
        )

        # Check if it's time to send daily report
        try:
            check_and_send_report()
        except Exception as e:
            log.error(f"Report scheduler error: {e}")


# ── Entry point ───────────────────────────────────────────
def main():
    """Main entry point for the MNQ Trading Agent."""
    import threading

    print("=" * 60)
    print("  MNQ Trading Agent v2 — Multi-Timeframe Edition")
    print(f"  Trigger TFs : {', '.join(TRIGGER_TIMEFRAMES)}")
    print(f"  Min alignment: {MIN_TF_ALIGNMENT}/4 timeframes")
    print(f"  Alert cooldown: {ALERT_COOLDOWN_SECS}s")
    print("=" * 60)

    # Register bar-close callback
    fetcher.set_bar_close_callback(on_bar_close)

    # Start market data feeds
    fetcher.start()
    spy_fetcher.start()

    # Wait for initial data load
    log.info("Waiting for initial bar buffers to fill...")
    if fetcher.wait_for_data(min_bars=20, timeout=120):
        log.info("All timeframe buffers ready. Monitoring for sweeps...")
    else:
        log.warning("Timeout waiting for data — continuing anyway.")

    # Give SPY fetcher a moment to get first quote
    time.sleep(2)
    if spy_fetcher.connected:
        log.info(f"SPY price: {spy_fetcher.get_price():.2f}")
    else:
        log.warning("SPY fetcher not yet connected — will retry.")

    # Status printer in background
    threading.Thread(target=status_loop, daemon=True).start()

    # Market close monitor in background (detects 3:15 PM CT closes)
    log.info("Starting market close monitor (3:15 PM CT auto-close)...")
    threading.Thread(target=market_close_monitor_loop, daemon=True).start()

    # TP/SL monitor in background (monitors ALL alerts for hits)
    log.info("Starting TP/SL monitor (tracks all alerts)...")
    threading.Thread(target=tp_sl_monitor_loop, daemon=True).start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down.")


if __name__ == "__main__":
    main()
