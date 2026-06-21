"""
MNQ Trading Agent — Monitor
============================
Background monitoring thread that:
1. Continuously checks current MNQ price
2. Compares against pending alert SL/TP levels
3. Auto-records exits when levels are hit
4. Sends Discord notifications
5. Updates daily reports

Run: python src/monitoring/monitor.py
"""

import sys
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime
import pytz

# Setup path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.trading.trade_journal import TradeJournal
from src.data.config import DISCORD_WEBHOOK_URL

# MVC Imports
from src.controllers.trade_controller import TradeController
from src.controllers.monitor_controller import MonitorController
from src.database.alert_db import AlertDatabase
from src.database.trade_db import TradeDatabase
from src.services.price_service import PriceService
from src.views.discord_view import DiscordView

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("monitor")

tz = pytz.timezone("America/Chicago")
journal = TradeJournal()  # Kept for compatibility

# MVC Components
alert_db = AlertDatabase()
trade_db = TradeDatabase()
price_svc = PriceService()
trade_ctrl = TradeController(alert_db, trade_db)
monitor_ctrl = MonitorController(trade_ctrl)
discord_view = DiscordView()

# Market hours: 8:30 AM - 4:00 PM CT (includes pre-market and regular hours)
MARKET_OPEN = 8.5  # 8:30 AM
MARKET_CLOSE = 16.0  # 4:00 PM


def is_market_open() -> bool:
    """Check if market is currently open (8:30 AM - 4:00 PM CT)."""
    now = datetime.now(tz)
    hour = now.hour + (now.minute / 60)

    # Only weekdays
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    return MARKET_OPEN <= hour <= MARKET_CLOSE


def get_current_price() -> float:
    """Fetch current MNQ price via PriceService."""
    return price_svc.get_mnq_price()


def check_pending_alerts(current_price: float, discord_enabled: bool = True) -> None:
    """
    Check all pending alerts and record exits if SL/TP are hit.

    Args:
        current_price: Current MNQ price
        discord_enabled: Whether to send Discord notifications (default: True)
    """
    # Use MonitorController to check alerts
    recorded_trades = monitor_ctrl.check_pending_alerts(current_price)

    if not recorded_trades:
        return

    # Send Discord notifications for recorded exits (if enabled)
    if discord_enabled:
        for trade in recorded_trades:
            # Get the alert for context
            alert = alert_db.get_by_id(trade.alert_id)
            if alert:
                discord_view.send_exit(trade, alert)
    else:
        # Still log the exits even if Discord is disabled
        for trade in recorded_trades:
            log.info(f"[No Discord] Trade recorded: Alert {trade.alert_id} {trade.exit_type} @ ${trade.exit_price:.2f}")

def main():
    """Main monitoring loop."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="MNQ Trading Agent — Monitor for SL/TP exits"
    )
    parser.add_argument(
        "--discord-off",
        action="store_true",
        default=False,
        help="Disable Discord notifications (default: enabled)"
    )
    parser.add_argument(
        "--discord-on",
        action="store_true",
        default=False,
        help="Enable Discord notifications (default: enabled)"
    )
    args = parser.parse_args()

    # Determine Discord setting
    discord_enabled = not args.discord_off

    log.info("=" * 70)
    log.info("MNQ Trading Agent — Monitor Started")
    log.info("=" * 70)
    log.info("Monitoring for SL/TP exits during market hours (8:30 AM - 4:00 PM CT)")
    if discord_enabled:
        log.info("Discord notifications: ENABLED ✓")
    else:
        log.info("Discord notifications: DISABLED")
    log.info("")

    consecutive_errors = 0
    max_errors = 5

    while True:
        try:
            if not is_market_open():
                log.debug("Market closed, sleeping...")
                time.sleep(60)
                continue

            # Fetch current price
            current_price = get_current_price()
            if current_price is None:
                consecutive_errors += 1
                if consecutive_errors >= max_errors:
                    log.error(f"Max consecutive errors ({max_errors}) reached, exiting")
                    break
                time.sleep(10)
                continue

            # Reset error counter on success
            consecutive_errors = 0

            # Check pending alerts
            check_pending_alerts(current_price, discord_enabled)

            # Sleep for 5 seconds before next check
            time.sleep(5)

        except KeyboardInterrupt:
            log.info("Monitor stopped by user")
            break
        except Exception as e:
            log.error(f"Unexpected error in monitor loop: {e}", exc_info=True)
            consecutive_errors += 1
            if consecutive_errors >= max_errors:
                log.error(f"Max consecutive errors ({max_errors}) reached, exiting")
                break
            time.sleep(10)


if __name__ == "__main__":
    main()
