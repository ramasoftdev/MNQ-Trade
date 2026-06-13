"""Database access for Alert model."""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from src.models.alert import Alert

log = logging.getLogger("alert_db")

DB_PATH = Path(__file__).parent.parent.parent / "src" / "trading" / "trades.db"


class AlertDatabase:
    """Database operations for alerts."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)

    def save(self, alert: Alert) -> int:
        """
        Save alert to database.

        Returns: alert_id
        """
        if not alert.is_valid():
            raise ValueError(f"Invalid alert: {alert}")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            ts = alert.timestamp
            date = ts.date() if hasattr(ts, "date") else datetime.fromisoformat(str(ts)).date()

            cursor.execute(
                """
                INSERT INTO alerts (
                    timestamp, date, direction, entry_price, stop_loss, take_profit, trigger_tf,
                    confluence_score, base_score, ext_score, spy_magnet_score,
                    sweep_confirmed, reversal_candle, near_poc, vwap_confluence,
                    tf_1h_aligned, tf_3plus_aligned, rth_session,
                    current_vwap, current_poc, spy_price,
                    probability, assessment, confidence, reasoning, trade_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    date,
                    alert.direction,
                    alert.entry_price,
                    alert.stop_loss,
                    alert.take_profit,
                    alert.trigger_tf,
                    alert.confluence_score,
                    alert.base_score,
                    alert.ext_score,
                    alert.spy_magnet_score,
                    alert.sweep_confirmed,
                    alert.reversal_candle,
                    alert.near_poc,
                    alert.vwap_confluence,
                    alert.tf_1h_aligned,
                    alert.tf_3plus_aligned,
                    alert.rth_session,
                    alert.current_vwap,
                    alert.current_poc,
                    alert.spy_price,
                    alert.probability,
                    alert.assessment,
                    alert.confidence,
                    alert.reasoning,
                    alert.trade_status,
                ),
            )
            conn.commit()

            alert_id = cursor.lastrowid
            log.info(f"Alert saved: id={alert_id}, direction={alert.direction}, score={alert.confluence_score}")
            return alert_id

    def get_by_id(self, alert_id: int) -> Optional[Alert]:
        """Load alert by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_alert(row)

    def get_pending(self) -> List[Alert]:
        """Get all PENDING alerts with SL/TP set."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM alerts
                WHERE stop_loss IS NOT NULL
                AND take_profit IS NOT NULL
                AND trade_status = 'PENDING'
                AND tp_sl_notified = 0
                ORDER BY timestamp DESC
                """
            )
            return [self._row_to_alert(row) for row in cursor.fetchall()]

    def get_by_date(self, date_str: str) -> List[Alert]:
        """Get all alerts for a specific date (YYYY-MM-DD)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts WHERE date = ? ORDER BY timestamp ASC", (date_str,))
            return [self._row_to_alert(row) for row in cursor.fetchall()]

    def update_status(self, alert_id: int, status: str, hit_time: Optional[datetime] = None):
        """Update alert trade status."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if hit_time:
                cursor.execute(
                    """
                    UPDATE alerts
                    SET trade_status = ?, tp_sl_notified = 1, tp_sl_hit_at = ?
                    WHERE id = ?
                    """,
                    (status, hit_time, alert_id),
                )
            else:
                cursor.execute(
                    "UPDATE alerts SET trade_status = ? WHERE id = ?",
                    (status, alert_id),
                )

            conn.commit()
            log.info(f"Alert {alert_id} status updated to {status}")

    def get_all(self) -> List[Alert]:
        """Get all alerts."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts ORDER BY timestamp DESC")
            return [self._row_to_alert(row) for row in cursor.fetchall()]

    @staticmethod
    def _row_to_alert(row) -> Alert:
        """Convert database row to Alert model."""
        return Alert(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            direction=row["direction"],
            entry_price=row["entry_price"],
            confluence_score=row["confluence_score"],
            trigger_tf=row["trigger_tf"],
            stop_loss=row["stop_loss"],
            take_profit=row["take_profit"],
            probability=row["probability"],
            assessment=row["assessment"],
            confidence=row["confidence"],
            reasoning=row["reasoning"],
            trade_status=row["trade_status"],
            sweep_confirmed=row["sweep_confirmed"],
            reversal_candle=row["reversal_candle"],
            near_poc=row["near_poc"],
            vwap_confluence=row["vwap_confluence"],
            tf_1h_aligned=row["tf_1h_aligned"],
            tf_3plus_aligned=row["tf_3plus_aligned"],
            rth_session=row["rth_session"],
            base_score=row["base_score"],
            ext_score=row["ext_score"],
            spy_magnet_score=row["spy_magnet_score"],
            current_vwap=row["current_vwap"],
            current_poc=row["current_poc"],
            spy_price=row["spy_price"],
            taken=row["taken"],
            tp_sl_notified=row["tp_sl_notified"],
            tp_sl_hit_at=row["tp_sl_hit_at"],
        )
