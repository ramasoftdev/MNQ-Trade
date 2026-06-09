#!/usr/bin/env python3
"""
Fill Trade CLI Tool & Alert Manager
====================================
Manage alerts, set SL/TP, record fills, and generate reports.

Workflow:
1. Agent detects sweep → Alert auto-saved as NOT TAKEN
2. You review alert and decide to take it:
   python fill_trade.py --alert-id=123 --take
   → Auto-calculates SL/TP based on confluence score

3. Optional: Update SL/TP:
   python fill_trade.py --alert-id=123 --update-sl=30440.00 --update-tp=30470.00

4. When trade closes, record exit:
   python fill_trade.py --alert-id=123 --exit-price=30450.50
   → Calculates P&L and marks alert as FILLED

Usage:
    # Mark alert as taken (auto-calculate SL/TP)
    python fill_trade.py --alert-id=123 --take

    # Mark as taken with custom SL/TP
    python fill_trade.py --alert-id=123 --take --stop-loss=30440.00 --take-profit=30470.00

    # Update SL/TP for existing taken alert
    python fill_trade.py --alert-id=123 --update-sl=30445.00 --update-tp=30465.00

    # Record a fill (exit price)
    python fill_trade.py --alert-id=123 --exit-price=30450.50

    # View all alerts with status
    python fill_trade.py --list-pending

    # Generate report
    python fill_trade.py --report "2026-06-05"
"""

import argparse
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
import sys

from src.trading.trade_journal import TradeJournal
from src.reporting.daily_report import DailyReport
import pytz

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fill_trade")
TZ = pytz.timezone("America/Chicago")


def mark_alert_taken(
    alert_id: int,
    stop_loss: float = None,
    take_profit: float = None,
):
    """Mark an alert as taken with optional custom SL/TP."""
    journal = TradeJournal()

    # Validate alert exists
    alert = journal.get_alert(alert_id)
    if not alert:
        log.error(f"Alert {alert_id} not found")
        return False

    try:
        journal.mark_as_taken(alert_id, stop_loss, take_profit)
        log.info(f"✓ Alert marked as taken")
        return True
    except Exception as e:
        log.error(f"Failed to mark alert as taken: {e}")
        return False


def update_alert_sl_tp(
    alert_id: int,
    stop_loss: float = None,
    take_profit: float = None,
):
    """Update SL/TP for an existing taken alert."""
    journal = TradeJournal()

    # Validate alert exists
    alert = journal.get_alert(alert_id)
    if not alert:
        log.error(f"Alert {alert_id} not found")
        return False

    try:
        journal.update_sl_tp(alert_id, stop_loss, take_profit)
        log.info(f"✓ SL/TP updated")
        return True
    except Exception as e:
        log.error(f"Failed to update SL/TP: {e}")
        return False


def record_fill(alert_id: int, exit_price: float, exit_time: str = None, notes: str = None):
    """Record a trade fill."""
    journal = TradeJournal()

    # Validate alert exists
    alert = journal.get_alert(alert_id)
    if not alert:
        log.error(f"Alert {alert_id} not found")
        return False

    # Parse exit time
    if exit_time:
        try:
            # Try multiple formats
            for fmt in ["%H:%M:%S", "%H:%M", "%Y-%m-%d %H:%M:%S"]:
                try:
                    dt = datetime.strptime(exit_time, fmt)
                    # If just time, use today's date
                    if fmt in ["%H:%M:%S", "%H:%M"]:
                        now = datetime.now(TZ)
                        dt = dt.replace(year=now.year, month=now.month, day=now.day)
                    break
                except ValueError:
                    continue
            else:
                log.error(f"Invalid time format: {exit_time}")
                return False
        except Exception as e:
            log.error(f"Error parsing exit time: {e}")
            return False
    else:
        dt = datetime.now(TZ)

    # Record the fill
    try:
        journal.record_fill(alert_id, exit_price, dt, notes)
        log.info(f"✓ Trade filled successfully")
        return True
    except Exception as e:
        log.error(f"Failed to record fill: {e}")
        return False


def list_pending_alerts():
    """Show all pending alerts with SL/TP."""
    journal = TradeJournal()

    # Get today's alerts
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    alerts = journal.get_alerts_by_date(today)

    if not alerts:
        log.info(f"No alerts for {today}")
        return

    # Separate by status and taken flag
    # Note: alerts tuple format has changed, need to access by column index
    # For now, we'll use a dict approach by querying each alert
    pending_untaken = []
    pending_taken = []
    filled = []

    with sqlite3.connect(journal.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM alerts WHERE date = ? ORDER BY timestamp ASC
            """,
            (today,),
        )
        all_alerts = [dict(row) for row in cursor.fetchall()]

    for alert in all_alerts:
        if alert["trade_status"] == "FILLED":
            filled.append(alert)
        elif alert["taken"]:
            pending_taken.append(alert)
        else:
            pending_untaken.append(alert)

    print("\n" + "=" * 110)
    print(f"  ALERT STATUS — {today}")
    print("=" * 110)

    if pending_untaken:
        print(f"\n⏳ NOT TAKEN ({len(pending_untaken)} alerts):\n")
        for alert in pending_untaken:
            alert_id = alert["id"]
            timestamp = alert["timestamp"]
            direction = alert["direction"]
            entry_price = alert["entry_price"]
            confluence = alert["confluence_score"]
            assessment = alert["assessment"]

            print(f"  ID {alert_id:4d} | {timestamp[11:16]} | {direction:5} @ {entry_price:8.2f} | "
                  f"Score {confluence:4.1f} | {assessment:6}")

    if pending_taken:
        print(f"\n✋ TAKEN ({len(pending_taken)} alerts with SL/TP set):\n")
        for alert in pending_taken:
            alert_id = alert["id"]
            direction = alert["direction"]
            entry_price = alert["entry_price"]
            sl = alert["stop_loss"]
            tp = alert["take_profit"]
            confluence = alert["confluence_score"]

            print(f"  ID {alert_id:4d} | {direction:5} | E:{entry_price:8.2f} | "
                  f"SL:{sl:8.2f} | TP:{tp:8.2f} | Score {confluence:4.1f}")

    if filled:
        print(f"\n✓ FILLED ({len(filled)} trades closed):\n")
        for alert in filled:
            alert_id = alert["id"]
            direction = alert["direction"]
            entry_price = alert["entry_price"]

            # Get trade details
            trade = journal.get_trade(alert_id)
            if trade:
                exit_price = trade[5]
                pnl = trade[8]
                result = trade[10]
                pnl_pct = trade[9]
                exit_type = trade[12] if len(trade) > 12 else "UNKNOWN"
                pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
                result_emoji = "✓" if result == "WIN" else "✗"

                # Map exit type to emoji
                exit_emoji = {
                    "TP_HIT": "📍",
                    "SL_HIT": "⛔",
                    "MANUAL_EXIT": "✋",
                    "BREAK_EVEN": "🔄"
                }.get(exit_type, "")

                print(f"  ID {alert_id:4d} | {direction:5} | {entry_price:8.2f} → {exit_price:8.2f} | "
                      f"{pnl_str:>10} ({pnl_pct:+.1f}%) {result_emoji} {exit_emoji} {exit_type}")

    print("\n" + "=" * 110 + "\n")


def generate_report(date_str: str = None):
    """Generate and display daily report."""
    if not date_str:
        date_str = datetime.now(TZ).strftime("%Y-%m-%d")

    reporter = DailyReport()
    report = reporter.generate_report(date_str)

    # Print text report
    print("\n" + report.to_text() + "\n")

    # Save HTML
    html_path = report.to_html()
    log.info(f"HTML report saved: {html_path}")


def show_exit_analysis(date_str: str = None):
    """Show analysis of how trades exited (TP hit, SL hit, manual exit)."""
    journal = TradeJournal()

    if not date_str:
        date_str = datetime.now(TZ).strftime("%Y-%m-%d")

    stats = journal.get_exit_type_stats(date_str)

    print("\n" + "=" * 100)
    print(f"  EXIT TYPE ANALYSIS — {date_str}")
    print("=" * 100)

    print("\nHow did trades exit by confluence score band?\n")
    print(f"{'Band':<8} {'Total':>6} {'TP Hit':>10} {'SL Hit':>10} {'Manual':>10} {'BE':>6} {'TP Rate':>10}")
    print("-" * 100)

    for band in sorted(stats.keys(), key=lambda x: -float(x.split('+')[0] if '+' in x else x.split('-')[0])):
        s = stats[band]
        tp_rate = s.get("tp_hit_rate", 0)
        print(
            f"{band:<8} {s['total']:>6} {s['tp_hit']:>10} {s['sl_hit']:>10} "
            f"{s['manual_exit']:>10} {s['break_even']:>6} {tp_rate:>9.1f}%"
        )

    print("\n" + "=" * 100)
    print("\nInterpretation:")
    print("  TP Hit:     Trade reached take profit (strategy worked)")
    print("  SL Hit:     Trade hit stop loss (setup was wrong)")
    print("  Manual:     You exited manually (between SL and TP)")
    print("  BE:         Trade exited at breakeven")
    print("  TP Rate:    % of trades that hit TP (success rate)")
    print("\nGoal: High confluence (10+) should have 70%+ TP hit rate")
    print("=" * 100 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Manage alerts, record fills, and generate reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Mark an alert as taken (auto-calculate SL/TP)
  python fill_trade.py --alert-id=123 --take

  # Mark as taken with custom SL/TP
  python fill_trade.py --alert-id=123 --take --stop-loss=30440.00 --take-profit=30470.00

  # Update SL/TP for existing taken alert
  python fill_trade.py --alert-id=123 --update-sl=30445.00 --update-tp=30465.00

  # Record a fill (exit price)
  python fill_trade.py --alert-id=123 --exit-price=30450.50
  python fill_trade.py --alert-id=456 --exit-price=30420.25 --exit-time="14:35:00" --notes="Hit target"

  # View alerts
  python fill_trade.py --list-pending

  # Generate report
  python fill_trade.py --report "2026-06-05"
        """,
    )

    parser.add_argument("--alert-id", type=int, help="Alert ID to manage")
    parser.add_argument("--take", action="store_true", help="Mark alert as taken (auto-calculate SL/TP)")
    parser.add_argument("--stop-loss", type=float, help="Custom stop loss (with --take)")
    parser.add_argument("--take-profit", type=float, help="Custom take profit (with --take)")
    parser.add_argument("--update-sl", type=float, help="Update stop loss for existing taken alert")
    parser.add_argument("--update-tp", type=float, help="Update take profit for existing taken alert")
    parser.add_argument("--exit-price", type=float, help="Exit price for recording a fill")
    parser.add_argument("--exit-time", type=str, help="Exit time (HH:MM:SS or HH:MM, default: now)")
    parser.add_argument("--notes", type=str, help="Notes about the fill")
    parser.add_argument("--list-pending", action="store_true", help="Show all alerts with status")
    parser.add_argument("--report", type=str, nargs="?", const=None, help="Generate report (optional: YYYY-MM-DD, default: today)")
    parser.add_argument("--exit-analysis", type=str, nargs="?", const=None, help="Show exit type analysis (optional: YYYY-MM-DD, default: today)")

    args = parser.parse_args()

    # Validate arguments
    if args.alert_id:
        if args.take:
            # Mark as taken
            success = mark_alert_taken(args.alert_id, args.stop_loss, args.take_profit)
            sys.exit(0 if success else 1)
        elif args.update_sl is not None or args.update_tp is not None:
            # Update SL/TP
            success = update_alert_sl_tp(args.alert_id, args.update_sl, args.update_tp)
            sys.exit(0 if success else 1)
        elif args.exit_price:
            # Record fill
            success = record_fill(args.alert_id, args.exit_price, args.exit_time, args.notes)
            sys.exit(0 if success else 1)
        else:
            log.error("With --alert-id, use --take, --update-sl/--update-tp, or --exit-price")
            sys.exit(1)
    elif args.list_pending:
        list_pending_alerts()
    elif args.report is not None:
        generate_report(args.report)
    elif args.exit_analysis is not None:
        show_exit_analysis(args.exit_analysis)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
