"""Discord presentation layer."""

import logging
import requests
from datetime import datetime
import pytz

from src.models.alert import Alert
from src.models.trade import Trade
from src.data.config import DISCORD_WEBHOOK_URL, TIMEZONE

log = logging.getLogger("discord_view")
TZ = pytz.timezone(TIMEZONE)


class DiscordView:
    """Handles Discord alert and notification formatting."""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or DISCORD_WEBHOOK_URL

    def send_alert(self, alert: Alert) -> bool:
        """Send alert notification to Discord."""
        if not self.webhook_url:
            log.warning("Discord webhook not configured")
            return False

        try:
            embed = self._build_alert_embed(alert)
            payload = {"embeds": [embed]}
            response = requests.post(self.webhook_url, json=payload, timeout=10)

            if response.status_code == 204:
                log.info(f"Alert #{alert.id} sent to Discord")
                return True
            else:
                log.warning(f"Discord error {response.status_code}: {response.text[:200]}")
                return False

        except Exception as e:
            log.error(f"Failed to send alert to Discord: {e}")
            return False

    def send_exit(self, trade: Trade, alert: Alert) -> bool:
        """Send exit notification to Discord."""
        if not self.webhook_url:
            log.warning("Discord webhook not configured")
            return False

        try:
            embed = self._build_exit_embed(trade, alert)
            payload = {"embeds": [embed]}
            response = requests.post(self.webhook_url, json=payload, timeout=10)

            if response.status_code == 204:
                log.info(f"Exit alert #{trade.alert_id} ({trade.exit_type}) sent to Discord")
                return True
            else:
                log.warning(f"Discord error {response.status_code}: {response.text[:200]}")
                return False

        except Exception as e:
            log.error(f"Failed to send exit to Discord: {e}")
            return False

    def _build_alert_embed(self, alert: Alert) -> dict:
        """Build Discord embed for new alert."""
        color = 0x2ECC71 if alert.assessment == "take" else (
            0xF0B429 if alert.assessment == "watch" else 0xE74C3C
        )

        timestamp = datetime.now(TZ).isoformat()

        fields = [
            {"name": "Direction", "value": alert.direction, "inline": True},
            {"name": "Score", "value": f"{alert.confluence_score:.1f}", "inline": True},
            {"name": "Entry", "value": f"${alert.entry_price:.2f}", "inline": True},
            {"name": "Assessment", "value": alert.assessment.upper(), "inline": True},
            {"name": "Confidence", "value": alert.confidence.upper(), "inline": True},
            {"name": "Probability", "value": f"{alert.probability}%", "inline": True},
        ]

        if alert.has_targets():
            fields.extend([
                {"name": "SL", "value": f"${alert.stop_loss:.2f}", "inline": True},
                {"name": "TP", "value": f"${alert.take_profit:.2f}", "inline": True},
            ])

        return {
            "title": f"LONG Alert #{alert.id}" if alert.direction == "LONG" else f"SHORT Alert #{alert.id}",
            "color": color,
            "fields": fields,
            "timestamp": timestamp,
            "footer": {"text": "MNQ Agent v2"}
        }

    def _build_exit_embed(self, trade: Trade, alert: Alert) -> dict:
        """Build Discord embed for trade exit."""
        emoji = "📍" if trade.exit_type == "TP_HIT" else "⛔"
        color = 0x2ECC71 if trade.exit_type == "TP_HIT" else 0xE74C3C

        timestamp = datetime.now(TZ).isoformat()

        return {
            "title": f"{emoji} Alert #{trade.alert_id} — {trade.exit_type}",
            "description": f"**Direction:** {trade.direction}\n**Result:** {trade.result}",
            "color": color,
            "fields": [
                {"name": "Entry", "value": f"${trade.entry_price:.2f}", "inline": True},
                {"name": "Exit", "value": f"${trade.exit_price:.2f}", "inline": True},
                {"name": "P&L", "value": f"${trade.pnl:.2f}", "inline": True},
                {"name": "Return", "value": f"{trade.pnl_percent:+.2f}%", "inline": True},
                {"name": "SL", "value": f"${trade.stop_loss_price:.2f}" if trade.stop_loss_price else "N/A", "inline": True},
                {"name": "TP", "value": f"${trade.take_profit_price:.2f}" if trade.take_profit_price else "N/A", "inline": True},
            ],
            "timestamp": timestamp,
            "footer": {"text": "MNQ Monitor"}
        }

    def send_error(self, message: str) -> bool:
        """Send error alert to Discord."""
        if not self.webhook_url:
            return False

        try:
            payload = {
                "embeds": [{
                    "title": "MNQ Agent — Error",
                    "description": message,
                    "color": 0xE74C3C,
                    "footer": {"text": "MNQ Agent v2"},
                }]
            }
            requests.post(self.webhook_url, json=payload, timeout=10)
            return True
        except Exception as e:
            log.error(f"Failed to send error to Discord: {e}")
            return False
