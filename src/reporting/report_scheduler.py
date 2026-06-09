"""
Report Scheduler
================
Generates and sends daily reports at market close.
Can run as a standalone service or be integrated into agent.

Usage:
    # Run as standalone service
    python report_scheduler.py

    # Or from agent
    import report_scheduler
    report_scheduler.check_and_send_report()
"""

import logging
import time
from datetime import datetime
import pytz
import requests

from src.data.config import DAILY_REPORT_TIME, DISCORD_WEBHOOK_URL, TIMEZONE
from src.reporting.daily_report import DailyReport

log = logging.getLogger("report_scheduler")
TZ = pytz.timezone(TIMEZONE)


# Track which dates we've already sent reports for (prevent duplicates)
_reports_sent = set()


def should_generate_report() -> bool:
    """Check if it's time to generate today's report."""
    now = datetime.now(TZ)
    report_hour, report_minute = DAILY_REPORT_TIME

    # Check if we're at or past the report time
    is_time = now.hour == report_hour and now.minute >= report_minute
    today = now.strftime("%Y-%m-%d")

    # Only send once per day
    already_sent = today in _reports_sent

    return is_time and not already_sent


def send_report_to_discord(embed_payload: dict) -> bool:
    """Send report embed to Discord webhook."""
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=embed_payload, timeout=10)
        if resp.status_code == 204:
            log.info("✓ Daily report sent to Discord")
            return True
        else:
            log.error(f"Discord error {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        log.error(f"Failed to send report to Discord: {e}")
        return False


def check_and_send_report() -> bool:
    """
    Check if it's time to send a report, and send if needed.
    Safe to call frequently (e.g., every minute).

    Returns:
        True if report was sent, False otherwise
    """
    if not should_generate_report():
        return False

    now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")

    log.info(f"Generating daily report for {today}...")

    try:
        reporter = DailyReport()
        report = reporter.generate_report(today)

        # Format as Discord embed
        embed_payload = report.to_discord_embed()

        # Send to Discord
        success = send_report_to_discord(embed_payload)

        if success:
            _reports_sent.add(today)
            # Also save HTML
            html_path = report.to_html()
            log.info(f"Report archived: {html_path}")

        return success

    except Exception as e:
        log.error(f"Failed to generate report: {e}")
        return False


def run_scheduler():
    """Run report scheduler as a standalone service."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("=" * 70)
    log.info("  MNQ Trading Agent — Report Scheduler")
    log.info(f"  Daily report time: {DAILY_REPORT_TIME[0]:02d}:{DAILY_REPORT_TIME[1]:02d} CT")
    log.info("=" * 70)

    while True:
        try:
            check_and_send_report()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            log.info("Report scheduler stopped.")
            break
        except Exception as e:
            log.error(f"Scheduler error: {e}")
            time.sleep(60)


if __name__ == "__main__":
    run_scheduler()
