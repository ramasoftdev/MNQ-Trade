"""Database access for Trade model."""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from src.models.trade import Trade

log = logging.getLogger("trade_db")

DB_PATH = Path(__file__).parent.parent.parent / "src" / "trading" / "trades.db"


class TradeDatabase:
    """Database operations for trades."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)

    def save(self, trade: Trade) -> int:
        """
        Save trade to database.

        Returns: trade_id
        """
        if not trade.is_valid():
            raise ValueError(f"Invalid trade: {trade}")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            entry_ts = trade.entry_time.timestamp() if hasattr(trade.entry_time, "timestamp") else datetime.fromisoformat(str(trade.entry_time)).timestamp()
            exit_ts = trade.exit_time.timestamp() if hasattr(trade.exit_time, "timestamp") else datetime.fromisoformat(str(trade.exit_time)).timestamp()

            cursor.execute(
                """
                INSERT INTO trades (
                    alert_id, entry_price, entry_time, entry_ts,
                    exit_price, exit_time, exit_ts,
                    pnl, pnl_percent, hold_seconds, result, notes,
                    exit_type, stop_loss_price, take_profit_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.alert_id,
                    trade.entry_price,
                    trade.entry_time,
                    entry_ts,
                    trade.exit_price,
                    trade.exit_time,
                    exit_ts,
                    round(trade.pnl, 2),
                    round(trade.pnl_percent, 2),
                    trade.hold_seconds,
                    trade.result,
                    trade.notes,
                    trade.exit_type,
                    trade.stop_loss_price,
                    trade.take_profit_price,
                ),
            )
            conn.commit()

            trade_id = cursor.lastrowid
            log.info(
                f"Trade saved: id={trade_id}, alert={trade.alert_id}, "
                f"pnl=${trade.pnl:.2f} ({trade.pnl_percent:.2f}%), "
                f"result={trade.result}, exit_type={trade.exit_type}"
            )
            return trade_id

    def get_by_id(self, trade_id: int) -> Optional[Trade]:
        """Load trade by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_trade(row)

    def get_by_alert_id(self, alert_id: int) -> Optional[Trade]:
        """Load trade by alert ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE alert_id = ?", (alert_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_trade(row)

    def get_by_date(self, date_str: str) -> List[Trade]:
        """Get all trades for a specific date (YYYY-MM-DD)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT t.* FROM trades t
                JOIN alerts a ON t.alert_id = a.id
                WHERE a.date = ?
                ORDER BY t.entry_time ASC
                """,
                (date_str,),
            )
            return [self._row_to_trade(row) for row in cursor.fetchall()]

    def get_all(self) -> List[Trade]:
        """Get all trades."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades ORDER BY entry_time DESC")
            return [self._row_to_trade(row) for row in cursor.fetchall()]

    def get_by_date_range(self, start_date: str, end_date: str) -> List[Trade]:
        """Get trades for a date range (YYYY-MM-DD)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT t.* FROM trades t
                JOIN alerts a ON t.alert_id = a.id
                WHERE a.date BETWEEN ? AND ?
                ORDER BY t.entry_time DESC
                """,
                (start_date, end_date),
            )
            return [self._row_to_trade(row) for row in cursor.fetchall()]

    def get_by_exit_type(self, exit_type: str, date_str: str = None) -> List[Trade]:
        """Get trades by exit type (TP_HIT, SL_HIT, etc.)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if date_str:
                cursor.execute(
                    """
                    SELECT t.* FROM trades t
                    JOIN alerts a ON t.alert_id = a.id
                    WHERE t.exit_type = ? AND a.date = ?
                    ORDER BY t.entry_time DESC
                    """,
                    (exit_type, date_str),
                )
            else:
                cursor.execute(
                    "SELECT * FROM trades WHERE exit_type = ? ORDER BY entry_time DESC",
                    (exit_type,),
                )

            return [self._row_to_trade(row) for row in cursor.fetchall()]

    @staticmethod
    def _row_to_trade(row) -> Trade:
        """Convert database row to Trade model."""
        return Trade(
            id=row["id"],
            alert_id=row["alert_id"],
            entry_price=row["entry_price"],
            exit_price=row["exit_price"],
            direction="LONG",  # We'll get this from alert if needed
            exit_type=row["exit_type"],
            pnl=row["pnl"],
            pnl_percent=row["pnl_percent"],
            hold_seconds=row["hold_seconds"],
            entry_time=datetime.fromisoformat(row["entry_time"]),
            exit_time=datetime.fromisoformat(row["exit_time"]),
            stop_loss_price=row["stop_loss_price"],
            take_profit_price=row["take_profit_price"],
            result=row["result"],
            notes=row["notes"],
        )
