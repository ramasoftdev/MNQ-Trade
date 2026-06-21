"""
MNQ Trading Agent v3 — VWAP/POC System
======================================
Entry: 5m VWAP bounce + 15m MA confirmation
Context: Daily MAs for macro analysis
AI Analysis: Claude probability assessment

RUN:
  python src/core/run.py
  or
  python src/core/agent.py

HEALTH CHECK:
  Prints status every 60 seconds.
"""

import logging
import time
from datetime import datetime, timedelta
import pytz
import threading

from src.data.config import (
    ALERT_COOLDOWN_SECS, TIMEZONE, MA_PERIODS,
    CONFLUENCE_THRESHOLD, CONFLUENCE_MAX,
    VWAP_TOLERANCE_PTS, VOLUME_SPIKE_MULTIPLIER,
)
from src.data.data_fetcher import MultiTimeframeFetcher
from src.data.spy_fetcher import SpyFetcher
from src.analysis.vwap_analyzer import calculate_vwap, detect_vwap_bounce
from src.analysis.ma_analyzer import calculate_mas, check_ma_alignment, analyze_daily_mas
from src.analysis.volume_analyzer import detect_volume_spike, calculate_poc
from src.analysis.probability_engine import get_probability
from src.reporting.discord_formatter import send_to_discord
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
TZ = pytz.timezone(TIMEZONE)

# ── Global state ──────────────────────────────────────────
fetcher = MultiTimeframeFetcher()
spy_fetcher = SpyFetcher()
journal = TradeJournal()

# MVC Components
alert_db = AlertDatabase()
alert_ctrl = AlertController(alert_db)
discord_view = DiscordView()

_last_alert: dict = {}  # {direction: datetime} — cooldown tracker


# ── Cooldown helper ───────────────────────────────────────
def _is_cooled_down(direction: str) -> bool:
    last = _last_alert.get(direction)
    if last is None:
        return True
    return (datetime.now(TZ) - last).total_seconds() >= ALERT_COOLDOWN_SECS


def _record_alert(direction: str):
    _last_alert[direction] = datetime.now(TZ)


# ── MAIN DETECTION LOGIC ──────────────────────────────────
def check_vwap_bounce_signal(bars_5m, bars_15m, bars_1d, current_price):
    """
    Check for VWAP bounce entry signal.

    Returns:
        {
            "alert_triggered": bool,
            "direction": "LONG" or "SHORT",
            "confluence_score": 0-10,
            "entry_price": float,
            "stop_loss": float,
            "take_profit": float,
            "details": {...}
        }
        or None if no alert
    """

    if not bars_5m or not bars_15m or not bars_1d:
        return None

    # ── STEP 1: Calculate VWAP for both timeframes ──────────
    vwap_5m = calculate_vwap(bars_5m)
    vwap_15m = calculate_vwap(bars_15m)

    if vwap_5m is None or vwap_15m is None:
        return None

    # ── STEP 2: Detect 5m VWAP Bounce (PRIMARY ENTRY SIGNAL) ──
    bounce_long = detect_vwap_bounce(bars_5m, vwap_5m, current_price, direction="long")
    bounce_short = detect_vwap_bounce(bars_5m, vwap_5m, current_price, direction="short")

    bounce_detected = False
    direction = None

    if bounce_long.get("bounce_detected"):
        bounce_detected = True
        direction = "LONG"
        bounce_info = bounce_long
    elif bounce_short.get("bounce_detected"):
        bounce_detected = True
        direction = "SHORT"
        bounce_info = bounce_short

    if not bounce_detected:
        return None

    log.info(f"VWAP bounce detected: {direction}")

    # ── STEP 3: Check 15m MA Alignment (CONFIRMATION) ──────────
    mas_15m = calculate_mas(bars_15m, MA_PERIODS["15m"])
    ma5_15m = mas_15m.get("ma5")
    ma20_15m = mas_15m.get("ma20")
    ma50_15m = mas_15m.get("ma50")

    if any(ma is None for ma in [ma5_15m, ma20_15m, ma50_15m]):
        log.debug("15m MAs not ready, skipping")
        return None

    alignment_info = check_ma_alignment(ma5_15m, ma20_15m, ma50_15m)
    alignment = alignment_info.get("alignment", "none")

    # Confirm: 15m MAs must be aligned in same direction
    if direction == "LONG" and alignment != "bullish":
        log.debug(f"15m MAs not bullish aligned ({alignment}), skipping LONG")
        return None

    if direction == "SHORT" and alignment != "bearish":
        log.debug(f"15m MAs not bearish aligned ({alignment}), skipping SHORT")
        return None

    log.info(f"15m MAs confirmed {alignment} for {direction}")

    # ── STEP 4: Check Volume Confirmation ──────────────────────
    volume_info = detect_volume_spike(bars_5m, lookback=5, multiplier=VOLUME_SPIKE_MULTIPLIER)
    volume_spike = volume_info.get("spike_detected", False)

    if not volume_spike:
        log.debug(f"Volume spike not detected (ratio: {volume_info.get('spike_ratio', 0):.2f}x)")
        volume_score = 1  # Weak
    else:
        log.info(f"Volume spike confirmed ({volume_info.get('spike_ratio', 0):.2f}x)")
        volume_score = 2  # Strong

    # ── STEP 5: Calculate Confluence Score ──────────────────
    confluence_score = 0

    # VWAP bounce: +3 pts
    confluence_score += 3

    # Volume: +0-2 pts
    confluence_score += volume_score

    # 15m MA aligned: +2 pts
    confluence_score += 2

    # POC proximity: +1 pt (if price near POC)
    poc_5m = calculate_poc(bars_5m, lookback=24)
    if poc_5m and abs(current_price - poc_5m) < 5:
        confluence_score += 1

    # 15m MA5 proximity: +1 pt (if price near MA5)
    if abs(current_price - ma5_15m) < 5:
        confluence_score += 1

    log.info(f"Confluence Score: {confluence_score}/{CONFLUENCE_MAX} pts")

    # ── STEP 6: Check Alert Threshold ──────────────────────────
    if confluence_score < CONFLUENCE_THRESHOLD:
        log.info(f"Confluence score {confluence_score} < threshold {CONFLUENCE_THRESHOLD}, skipping")
        return None

    log.info(f"Confluence threshold met ({confluence_score}/{CONFLUENCE_MAX})")

    # ── STEP 7: Calculate TP/SL (from daily MAs) ──────────────
    daily_mas = calculate_mas(bars_1d, MA_PERIODS["1d"])
    daily_ma5 = daily_mas.get("ma5")
    daily_ma20 = daily_mas.get("ma20")
    daily_ma50 = daily_mas.get("ma50")

    # Set SL and TP based on daily MA structure
    if direction == "LONG":
        # SL below daily MA50 (major support)
        stop_loss = daily_ma50 - 5 if daily_ma50 else current_price - 15

        # TP at daily MA5 (daily resistance)
        take_profit = daily_ma5 + 5 if daily_ma5 else current_price + 20
    else:  # SHORT
        # SL above daily MA50 (major resistance)
        stop_loss = daily_ma50 + 5 if daily_ma50 else current_price + 15

        # TP at daily MA5 (daily support)
        take_profit = daily_ma5 - 5 if daily_ma5 else current_price - 20

    # ── STEP 8: Analyze Daily MA Context ──────────────────────
    daily_context = analyze_daily_mas(bars_1d, current_price)

    return {
        "alert_triggered": True,
        "direction": direction,
        "confluence_score": confluence_score,
        "entry_price": current_price,
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "details": {
            "vwap_5m": vwap_5m,
            "vwap_15m": vwap_15m,
            "poc_5m": poc_5m,
            "ma5_15m": ma5_15m,
            "ma20_15m": ma20_15m,
            "ma50_15m": ma50_15m,
            "ma5_1d": daily_ma5,
            "ma20_1d": daily_ma20,
            "ma50_1d": daily_ma50,
            "volume_spike_ratio": volume_info.get("spike_ratio", 0),
            "daily_context": daily_context,
            "alignment": alignment,
        }
    }


# ── Bar-close callback (called by data_fetcher on 5m close) ──
def on_bar_close(tf: str, bars: list):
    """
    Runs in background thread when 5m bar closes.
    Checks for VWAP bounce + 15m MA confirmation.
    """
    if tf != "5m":
        return  # Only trigger on 5m close

    log.info(f"5m bar closed ({len(bars)} bars in buffer)")

    # Get all TF buffers
    bars_5m = fetcher.get_bars("5m")
    bars_15m = fetcher.get_bars("15m")
    bars_1d = fetcher.get_bars("1d")

    if not all([bars_5m, bars_15m, bars_1d]):
        log.debug("Bars not ready yet")
        return

    # Current price
    current_price = bars_5m[-1].get("close", 0)

    # ── CHECK FOR ALERT ──────────────────────────────────────
    signal = check_vwap_bounce_signal(bars_5m, bars_15m, bars_1d, current_price)

    if not signal or not signal.get("alert_triggered"):
        return

    direction = signal["direction"]

    # Cooldown check
    if not _is_cooled_down(direction):
        log.info(f"Alert cooldown active for {direction} — skipping duplicate")
        return

    confluence_score = signal["confluence_score"]

    log.info(
        f"ALERT TRIGGERED: {direction} @ {current_price:.2f} | "
        f"Confluence: {confluence_score}/{CONFLUENCE_MAX} | "
        f"SL: {signal['stop_loss']:.2f} | TP: {signal['take_profit']:.2f}"
    )

    # ── CALL CLAUDE FOR PROBABILITY ASSESSMENT ──────────────
    prob_input = {
        "direction": direction,
        "entry_price": current_price,
        "stop_loss": signal["stop_loss"],
        "take_profit": signal["take_profit"],
        "confluence_score": confluence_score,
        "vwap_5m": signal["details"]["vwap_5m"],
        "vwap_15m": signal["details"]["vwap_15m"],
        "daily_context": signal["details"]["daily_context"],
        "timestamp": datetime.now(TZ).isoformat(),
    }

    prob = get_probability(prob_input)

    log.info(
        f"Claude: {prob.get('probability', 0)}% probability | "
        f"Confidence: {prob.get('confidence', '?')} | "
        f"Assessment: {prob.get('assessment', '?')}"
    )

    # Skip if Claude says "skip"
    if prob.get("assessment") == "skip":
        log.info("Claude assessment: SKIP — alert filtered out")
        return

    # ── CREATE ALERT ────────────────────────────────────────
    alert_data = {
        "timestamp": datetime.now(TZ),
        "direction": direction,
        "current_price": current_price,
        "stop_loss": signal["stop_loss"],
        "take_profit": signal["take_profit"],
        "confluence_score": confluence_score,
        "base_score": 3,  # VWAP bounce
        "ext_score": 0,   # Not used in new system
        "trigger_tf": "5m",
        "conditions": {
            "vwap_bounce": True,
            "ma_aligned": True,
            "volume_spike": signal["details"]["volume_spike_ratio"] > VOLUME_SPIKE_MULTIPLIER,
        },
        "vwap": signal["details"]["vwap_5m"],
        "poc": signal["details"]["poc_5m"],
        "probability": prob.get("probability", 0),
        "assessment": prob.get("assessment", "unknown"),
        "confidence": prob.get("confidence", "unknown"),
        "reasoning": prob.get("reasoning", ""),
        "daily_context": signal["details"]["daily_context"],
    }

    # Save alert to database
    try:
        alert = alert_ctrl.create_alert(alert_data)
        log.info(f"Alert saved: ID={alert.id}")
        _record_alert(direction)

        # Send to Discord
        try:
            discord_view.send_alert(alert)
            log.info("Discord notification sent")
        except Exception as e:
            log.error(f"Discord send failed: {e}")

    except Exception as e:
        log.error(f"Alert creation failed: {e}")


# ── Health check (prints every 60 seconds) ─────────────────
def health_check_loop():
    """Print status every 60 seconds."""
    while True:
        try:
            time.sleep(60)

            bars_5m = fetcher.get_bars("5m")
            bars_15m = fetcher.get_bars("15m")
            bars_1d = fetcher.get_bars("1d")

            mnq_price = bars_5m[-1]["close"] if bars_5m else 0
            spy_price = spy_fetcher.get_price() or 0

            log.info(
                f"STATUS  MNQ={mnq_price:.2f}  SPY={spy_price:.2f}  "
                f"bars 1d={len(bars_1d)} 15m={len(bars_15m)} 5m={len(bars_5m)}  "
                f"MNQ_connected={fetcher.connected}  SPY_connected={spy_fetcher.connected}"
            )

            # Check if it's time to send daily report
            try:
                check_and_send_report()
            except Exception as e:
                log.error(f"Report scheduler error: {e}")

        except Exception as e:
            log.error(f"Health check error: {e}")


# ── Entry point ───────────────────────────────────────────
def main():
    """Main entry point."""

    print("=" * 70)
    print("  MNQ Trading Agent v3 — VWAP/POC System")
    print(f"  Entry: 5m VWAP bounce + 15m MA confirmation")
    print(f"  Confluence threshold: {CONFLUENCE_THRESHOLD}/{CONFLUENCE_MAX} pts")
    print("=" * 70)

    # Register bar-close callback
    fetcher.set_bar_close_callback(on_bar_close)

    # Start market data feeds
    fetcher.start()
    spy_fetcher.start()

    # Start health check in background
    health_thread = threading.Thread(target=health_check_loop, daemon=True)
    health_thread.start()

    log.info("Waiting for initial bar buffers to fill...")
    if fetcher.wait_for_data(min_bars=20, timeout=120):
        log.info("All timeframe buffers ready. Monitoring for VWAP bounces...")
    else:
        log.warning("Timeout waiting for data — continuing anyway.")

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Agent stopped by user")


if __name__ == "__main__":
    main()
