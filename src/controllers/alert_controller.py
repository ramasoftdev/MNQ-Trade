"""Alert business logic controller."""

import logging
from typing import List, Optional

from src.models.alert import Alert
from src.database.alert_db import AlertDatabase

log = logging.getLogger("alert_controller")


class AlertController:
    """Handles alert creation, validation, and management."""

    def __init__(self, alert_db: AlertDatabase = None):
        self.alert_db = alert_db or AlertDatabase()

    def create_alert(self, alert_data: dict) -> Alert:
        """
        Create and save a new alert.

        Args:
            alert_data: Dictionary with alert information

        Returns:
            Alert model with ID set
        """
        # Create alert model
        alert = Alert(
            direction=alert_data.get("direction", "LONG"),
            entry_price=alert_data.get("current_price", 0),
            confluence_score=alert_data.get("confluence_score", 0),
            trigger_tf=alert_data.get("trigger_tf", "?"),
            stop_loss=alert_data.get("stop_loss", 0),
            take_profit=alert_data.get("take_profit", 0),
            probability=alert_data.get("probability", 0),
            assessment=alert_data.get("assessment", "UNKNOWN"),
            confidence=alert_data.get("confidence", "unknown"),
            reasoning=alert_data.get("reasoning", ""),
            sweep_confirmed=alert_data.get("conditions", {}).get("sweep_confirmed", False),
            reversal_candle=alert_data.get("conditions", {}).get("reversal_candle", False),
            near_poc=alert_data.get("conditions", {}).get("near_poc", False),
            vwap_confluence=alert_data.get("conditions", {}).get("vwap_confluence", False),
            tf_1h_aligned=alert_data.get("conditions", {}).get("1h_trend_aligned", False),
            tf_3plus_aligned=alert_data.get("conditions", {}).get("tf_3plus_aligned", False),
            rth_session=alert_data.get("conditions", {}).get("rth_session", False),
            base_score=alert_data.get("base_score", 0),
            ext_score=alert_data.get("ext_score", 0),
            spy_magnet_score=alert_data.get("spy_total_score", 0),
            current_vwap=alert_data.get("vwap", 0),
            current_poc=alert_data.get("poc_primary", 0),
            spy_price=alert_data.get("spy_price", 0),
        )

        # Validate
        if not alert.is_valid():
            raise ValueError(f"Invalid alert data: {alert_data}")

        # Save to database
        alert.id = self.alert_db.save(alert)

        log.info(f"Alert created: {alert}")
        return alert

    def get_alert(self, alert_id: int) -> Optional[Alert]:
        """Retrieve alert by ID."""
        alert = self.alert_db.get_by_id(alert_id)
        if not alert:
            log.warning(f"Alert {alert_id} not found")
        return alert

    def get_pending_alerts(self) -> List[Alert]:
        """Get all pending alerts with SL/TP set."""
        alerts = self.alert_db.get_pending()
        log.debug(f"Found {len(alerts)} pending alerts")
        return alerts

    def get_today_alerts(self, date_str: str) -> List[Alert]:
        """Get all alerts for today."""
        alerts = self.alert_db.get_by_date(date_str)
        log.debug(f"Found {len(alerts)} alerts for {date_str}")
        return alerts

    def update_alert_status(self, alert_id: int, status: str) -> bool:
        """Update alert trade status."""
        try:
            self.alert_db.update_status(alert_id, status)
            return True
        except Exception as e:
            log.error(f"Failed to update alert {alert_id} status: {e}")
            return False

    def mark_as_filled(self, alert_id: int) -> bool:
        """Mark alert as FILLED (trade completed)."""
        return self.update_alert_status(alert_id, "FILLED")

    def get_all_alerts(self) -> List[Alert]:
        """Get all alerts."""
        return self.alert_db.get_all()
