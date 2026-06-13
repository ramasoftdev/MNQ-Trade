"""
Trade Journal — SQLite Database for Alert & Trade Tracking
===========================================================
Persistent record of all alerts and trades.

Tables:
  - alerts: Every sweep alert with context
  - trades: Executed trades with P&L
  - daily_stats: Cached daily statistics
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("trade_journal")

DB_PATH = Path(__file__).parent / "trades.db"


class TradeJournal:
    """SQLite database for trade and alert tracking."""

    def __init__(self, db_path: str = None):
        """Initialize database connection and create schema if needed."""
        self.db_path = db_path or str(DB_PATH)
        self.init_db()

    def init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Alerts table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    date DATE,
                    direction TEXT,
                    entry_price REAL,
                    trigger_tf TEXT,
                    confluence_score REAL,
                    base_score INTEGER,
                    ext_score INTEGER,
                    spy_magnet_score REAL,

                    sweep_confirmed BOOLEAN,
                    reversal_candle BOOLEAN,
                    near_poc BOOLEAN,
                    vwap_confluence BOOLEAN,
                    tf_1h_aligned BOOLEAN,
                    tf_3plus_aligned BOOLEAN,
                    rth_session BOOLEAN,

                    current_vwap REAL,
                    current_poc REAL,
                    spy_price REAL,

                    probability INTEGER,
                    assessment TEXT,
                    confidence TEXT,
                    reasoning TEXT,

                    taken BOOLEAN DEFAULT 0,
                    taken_at DATETIME,
                    stop_loss REAL,
                    take_profit REAL,

                    tp_sl_notified BOOLEAN DEFAULT 0,
                    tp_sl_hit_at DATETIME,

                    trade_status TEXT DEFAULT 'PENDING',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Trades table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id INTEGER UNIQUE,
                    entry_price REAL,
                    entry_time DATETIME,
                    entry_ts REAL,

                    exit_price REAL,
                    exit_time DATETIME,
                    exit_ts REAL,

                    pnl REAL,
                    pnl_percent REAL,
                    hold_seconds INTEGER,
                    result TEXT,
                    notes TEXT,

                    exit_type TEXT,
                    stop_loss_price REAL,
                    take_profit_price REAL,

                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (alert_id) REFERENCES alerts(id)
                )
                """
            )

            # Daily stats cache
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE UNIQUE,
                    total_alerts INTEGER,
                    total_trades INTEGER,
                    trades_won INTEGER,
                    trades_lost INTEGER,
                    total_pnl REAL,
                    win_rate_pct REAL,
                    avg_pnl REAL,
                    avg_confluence REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.commit()
            log.info(f"Trade journal initialized at {self.db_path}")

    def log_alert(self, alert_data: dict) -> int:
        """
        Log a new alert to the database.

        Args:
            alert_data: Dictionary with alert context

        Returns:
            alert_id (int) — use for future fill tracking
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            ts = alert_data.get("timestamp", datetime.now())
            date = ts.date() if hasattr(ts, "date") else datetime.fromisoformat(ts).date()

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
                    alert_data.get("direction"),
                    alert_data.get("current_price", 0),
                    alert_data.get("stop_loss", 0),
                    alert_data.get("take_profit", 0),
                    alert_data.get("trigger_tf", "?"),
                    alert_data.get("confluence_score", 0),
                    alert_data.get("base_score", 0),
                    alert_data.get("ext_score", 0),
                    alert_data.get("spy_total_score", 0),
                    alert_data.get("conditions", {}).get("sweep_confirmed", False),
                    alert_data.get("conditions", {}).get("reversal_candle", False),
                    alert_data.get("conditions", {}).get("near_poc", False),
                    alert_data.get("conditions", {}).get("vwap_confluence", False),
                    alert_data.get("conditions", {}).get("1h_trend_aligned", False),
                    alert_data.get("conditions", {}).get("tf_3plus_aligned", False),
                    alert_data.get("conditions", {}).get("rth_session", False),
                    alert_data.get("vwap", 0),
                    alert_data.get("poc_primary", 0),
                    alert_data.get("spy_price", 0),
                    alert_data.get("probability", 0),
                    alert_data.get("assessment", "UNKNOWN"),
                    alert_data.get("confidence", "unknown"),
                    alert_data.get("reasoning", ""),
                    "PENDING",
                ),
            )
            conn.commit()

            alert_id = cursor.lastrowid
            log.info(f"Alert logged: id={alert_id}, direction={alert_data.get('direction')}, score={alert_data.get('confluence_score')}")
            return alert_id

    def _determine_exit_type(
        self,
        exit_price: float,
        entry_price: float,
        direction: str,
        stop_loss: float = None,
        take_profit: float = None,
    ) -> str:
        """
        Determine how the trade exited.

        Returns: "TP_HIT", "SL_HIT", "MANUAL_EXIT", or "BREAK_EVEN"
        """
        # Tolerance for floating point comparison (0.25 points)
        tolerance = 0.25

        # Check for breakeven first (within tolerance of entry)
        if abs(exit_price - entry_price) < tolerance:
            return "BREAK_EVEN"

        if stop_loss is None or take_profit is None:
            # No SL/TP set, classify as manual exit
            return "MANUAL_EXIT"

        if direction.upper() == "LONG":
            # For LONG: TP is above entry, SL is below entry
            if exit_price >= (take_profit - tolerance):
                return "TP_HIT"
            elif exit_price <= (stop_loss + tolerance):
                return "SL_HIT"
            else:
                return "MANUAL_EXIT"
        else:  # SHORT
            # For SHORT: TP is below entry, SL is above entry
            if exit_price <= (take_profit + tolerance):
                return "TP_HIT"
            elif exit_price >= (stop_loss - tolerance):
                return "SL_HIT"
            else:
                return "MANUAL_EXIT"

    def record_fill(
        self,
        alert_id: int,
        exit_price: float,
        exit_time: datetime = None,
        notes: str = None,
    ):
        """
        Record a trade fill (entry was in alert, now logging exit).

        Args:
            alert_id: ID from log_alert()
            exit_price: Price where trade exited
            exit_time: When trade exited (default: now)
            notes: Optional notes about the fill
        """
        exit_time = exit_time or datetime.now()
        exit_ts = exit_time.timestamp() if hasattr(exit_time, "timestamp") else datetime.fromisoformat(exit_time).timestamp()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get alert details
            cursor.execute(
                "SELECT entry_price, timestamp, direction, stop_loss, take_profit FROM alerts WHERE id = ?",
                (alert_id,),
            )
            result = cursor.fetchone()
            if not result:
                log.warning(f"Alert {alert_id} not found")
                return

            entry_price, entry_ts_str, direction, stop_loss, take_profit = result
            entry_ts = datetime.fromisoformat(entry_ts_str).timestamp()

            # Calculate P&L
            if direction == "LONG":
                pnl = (exit_price - entry_price) * 20  # MNQ multiplier ($20 per point)
                pnl_percent = ((exit_price - entry_price) / entry_price) * 100
            else:  # SHORT
                pnl = (entry_price - exit_price) * 20
                pnl_percent = ((entry_price - exit_price) / entry_price) * 100

            hold_seconds = int(exit_ts - entry_ts)
            result_str = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BREAK_EVEN")

            # Determine exit type (TP_HIT, SL_HIT, MANUAL_EXIT, BREAK_EVEN)
            exit_type = self._determine_exit_type(
                exit_price, entry_price, direction, stop_loss, take_profit
            )

            # Insert trade record
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
                    alert_id,
                    entry_price,
                    entry_ts_str,
                    entry_ts,
                    exit_price,
                    exit_time,
                    exit_ts,
                    round(pnl, 2),
                    round(pnl_percent, 2),
                    hold_seconds,
                    result_str,
                    notes or "",
                    exit_type,
                    stop_loss,
                    take_profit,
                ),
            )

            # Update alert status
            cursor.execute("UPDATE alerts SET trade_status = ? WHERE id = ?", ("FILLED", alert_id))

            conn.commit()
            log.info(
                f"Trade recorded: alert_id={alert_id}, direction={direction}, "
                f"exit={exit_price}, P&L=${pnl:.2f} ({pnl_percent:.2f}%), "
                f"result={result_str}, exit_type={exit_type}"
            )

    def calculate_sl_tp(
        self,
        entry_price: float,
        direction: str,
        confluence_score: float,
        atr: float = 20,
    ) -> tuple:
        """
        Auto-calculate stop loss and take profit based on confluence score.

        Higher confluence → wider TP, tighter SL
        Lower confluence → tighter TP, wider SL (more caution)

        Args:
            entry_price: Entry level
            direction: "LONG" or "SHORT"
            confluence_score: 0-12+
            atr: Average True Range (default 20 pts for MNQ)

        Returns:
            (stop_loss, take_profit) tuple
        """
        # Normalize confluence score to a multiplier (0.5x to 2.0x)
        # Score 4 = low confidence → 0.5x ATR
        # Score 12 = high confidence → 2.0x ATR
        confidence_mult = min(2.0, max(0.5, confluence_score / 6.0))

        # Calculate distances
        sl_distance = atr * 0.75 * confidence_mult  # Tighter SL for high confluence
        tp_distance = atr * 1.5 * confidence_mult   # Wider TP for high confluence

        if direction.upper() == "LONG":
            stop_loss = entry_price - sl_distance
            take_profit = entry_price + tp_distance
        else:  # SHORT
            stop_loss = entry_price + sl_distance
            take_profit = entry_price - tp_distance

        return round(stop_loss, 2), round(take_profit, 2)

    def mark_as_taken(
        self,
        alert_id: int,
        stop_loss: float = None,
        take_profit: float = None,
    ):
        """
        Mark an alert as taken and set SL/TP.

        Args:
            alert_id: Alert ID
            stop_loss: Custom SL (if None, auto-calculated)
            take_profit: Custom TP (if None, auto-calculated)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get alert details
            cursor.execute(
                "SELECT entry_price, direction, confluence_score FROM alerts WHERE id = ?",
                (alert_id,),
            )
            result = cursor.fetchone()
            if not result:
                log.warning(f"Alert {alert_id} not found")
                return

            entry_price, direction, confluence_score = result

            # Auto-calculate if not provided
            if stop_loss is None or take_profit is None:
                auto_sl, auto_tp = self.calculate_sl_tp(
                    entry_price, direction, confluence_score
                )
                stop_loss = stop_loss or auto_sl
                take_profit = take_profit or auto_tp

            # Update alert
            cursor.execute(
                """
                UPDATE alerts
                SET taken = 1, taken_at = ?, stop_loss = ?, take_profit = ?
                WHERE id = ?
                """,
                (datetime.now(), stop_loss, take_profit, alert_id),
            )
            conn.commit()

            log.info(
                f"Alert {alert_id} marked as TAKEN "
                f"| SL: {stop_loss:.2f} | TP: {take_profit:.2f}"
            )

    def update_sl_tp(
        self,
        alert_id: int,
        stop_loss: float = None,
        take_profit: float = None,
    ):
        """
        Update existing SL/TP for a taken alert.

        Args:
            alert_id: Alert ID
            stop_loss: New SL (or None to keep existing)
            take_profit: New TP (or None to keep existing)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if alert exists and is taken
            cursor.execute(
                "SELECT taken, stop_loss, take_profit FROM alerts WHERE id = ?",
                (alert_id,),
            )
            result = cursor.fetchone()
            if not result:
                log.warning(f"Alert {alert_id} not found")
                return

            taken, existing_sl, existing_tp = result
            if not taken:
                log.warning(f"Alert {alert_id} not marked as taken yet")
                return

            # Use provided values or keep existing
            new_sl = stop_loss if stop_loss is not None else existing_sl
            new_tp = take_profit if take_profit is not None else existing_tp

            cursor.execute(
                "UPDATE alerts SET stop_loss = ?, take_profit = ? WHERE id = ?",
                (new_sl, new_tp, alert_id),
            )
            conn.commit()

            log.info(f"Alert {alert_id} SL/TP updated | SL: {new_sl:.2f} | TP: {new_tp:.2f}")

    def get_alert(self, alert_id: int) -> dict:
        """Get a specific alert by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_trade(self, alert_id: int) -> dict:
        """Get a specific trade by alert ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE alert_id = ?", (alert_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_alerts_by_date(self, date_str: str) -> list:
        """Get all alerts for a specific date (YYYY-MM-DD)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts WHERE date = ? ORDER BY timestamp ASC", (date_str,))
            return [dict(row) for row in cursor.fetchall()]

    def get_trades_by_date(self, date_str: str) -> list:
        """Get all trades for a specific date (YYYY-MM-DD)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT t.*, a.direction FROM trades t
                JOIN alerts a ON t.alert_id = a.id
                WHERE a.date = ?
                ORDER BY t.entry_time ASC
                """,
                (date_str,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_daily_stats(self, date_str: str) -> dict:
        """
        Compute daily statistics for a date.

        Returns: {
            "date": "2026-06-05",
            "total_alerts": 8,
            "total_trades": 5,
            "trades_won": 3,
            "trades_lost": 2,
            "total_pnl": 1250.50,
            "win_rate_pct": 60.0,
            "avg_pnl": 250.10,
            "avg_confluence": 8.5,
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Total alerts
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE date = ?", (date_str,))
            total_alerts = cursor.fetchone()[0]

            # Trades for this date
            cursor.execute(
                """
                SELECT t.* FROM trades t
                JOIN alerts a ON t.alert_id = a.id
                WHERE a.date = ?
                """,
                (date_str,),
            )
            trades = cursor.fetchall()
            total_trades = len(trades)

            # Win/loss stats
            wins = sum(1 for t in trades if t[11] == "WIN")  # result is at index 11
            losses = sum(1 for t in trades if t[11] == "LOSS")

            # P&L
            total_pnl = sum(t[8] for t in trades) if trades else 0  # pnl is at index 8
            avg_pnl = total_pnl / total_trades if total_trades > 0 else 0

            # Win rate
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

            # Average confluence
            cursor.execute(
                "SELECT AVG(confluence_score) FROM alerts WHERE date = ?",
                (date_str,),
            )
            avg_confluence = cursor.fetchone()[0] or 0

            return {
                "date": date_str,
                "total_alerts": total_alerts,
                "total_trades": total_trades,
                "trades_won": wins,
                "trades_lost": losses,
                "total_pnl": round(total_pnl, 2),
                "win_rate_pct": round(win_rate, 1),
                "avg_pnl": round(avg_pnl, 2),
                "avg_confluence": round(avg_confluence, 2),
            }

    def get_date_range_stats(self, start_date: str, end_date: str) -> dict:
        """
        Get aggregated stats for a date range.

        Args:
            start_date: "YYYY-MM-DD"
            end_date: "YYYY-MM-DD"
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # All alerts in range
            cursor.execute(
                "SELECT COUNT(*) FROM alerts WHERE date BETWEEN ? AND ?",
                (start_date, end_date),
            )
            total_alerts = cursor.fetchone()[0]

            # All trades in range
            cursor.execute(
                """
                SELECT t.* FROM trades t
                JOIN alerts a ON t.alert_id = a.id
                WHERE a.date BETWEEN ? AND ?
                """,
                (start_date, end_date),
            )
            trades = cursor.fetchall()
            total_trades = len(trades)

            wins = sum(1 for t in trades if t[11] == "WIN")
            losses = sum(1 for t in trades if t[11] == "LOSS")

            total_pnl = sum(t[8] for t in trades) if trades else 0
            avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

            cursor.execute(
                "SELECT AVG(confluence_score) FROM alerts WHERE date BETWEEN ? AND ?",
                (start_date, end_date),
            )
            avg_confluence = cursor.fetchone()[0] or 0

            return {
                "start_date": start_date,
                "end_date": end_date,
                "total_alerts": total_alerts,
                "total_trades": total_trades,
                "trades_won": wins,
                "trades_lost": losses,
                "total_pnl": round(total_pnl, 2),
                "win_rate_pct": round(win_rate, 1),
                "avg_pnl": round(avg_pnl, 2),
                "avg_confluence": round(avg_confluence, 2),
            }

    def get_exit_type_stats(self, date_str: str = None, date_range: tuple = None) -> dict:
        """
        Analyze exit types (TP_HIT, SL_HIT, MANUAL_EXIT) by confidence band.

        Returns breakdown of how trades exited.

        Example:
            {
                "10+": {
                    "total": 5,
                    "tp_hit": 4,
                    "sl_hit": 0,
                    "manual_exit": 1,
                    "tp_hit_rate": 80.0,
                    "sl_hit_rate": 0.0
                },
                ...
            }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if date_str:
                query = """
                    SELECT
                        CASE
                            WHEN a.confluence_score >= 10 THEN '10+'
                            WHEN a.confluence_score >= 8 THEN '8-10'
                            WHEN a.confluence_score >= 5 THEN '5-8'
                            ELSE '<5'
                        END as band,
                        t.exit_type,
                        COUNT(*) as count
                    FROM trades t
                    JOIN alerts a ON t.alert_id = a.id
                    WHERE a.date = ?
                    GROUP BY band, t.exit_type
                """
                cursor.execute(query, (date_str,))
            elif date_range:
                start_date, end_date = date_range
                query = """
                    SELECT
                        CASE
                            WHEN a.confluence_score >= 10 THEN '10+'
                            WHEN a.confluence_score >= 8 THEN '8-10'
                            WHEN a.confluence_score >= 5 THEN '5-8'
                            ELSE '<5'
                        END as band,
                        t.exit_type,
                        COUNT(*) as count
                    FROM trades t
                    JOIN alerts a ON t.alert_id = a.id
                    WHERE a.date BETWEEN ? AND ?
                    GROUP BY band, t.exit_type
                """
                cursor.execute(query, (start_date, end_date))
            else:
                query = """
                    SELECT
                        CASE
                            WHEN a.confluence_score >= 10 THEN '10+'
                            WHEN a.confluence_score >= 8 THEN '8-10'
                            WHEN a.confluence_score >= 5 THEN '5-8'
                            ELSE '<5'
                        END as band,
                        t.exit_type,
                        COUNT(*) as count
                    FROM trades t
                    JOIN alerts a ON t.alert_id = a.id
                    GROUP BY band, t.exit_type
                """
                cursor.execute(query)

            results = cursor.fetchall()

            # Organize by band
            by_band = {}
            for band, exit_type, count in results:
                if band not in by_band:
                    by_band[band] = {"total": 0, "tp_hit": 0, "sl_hit": 0, "manual_exit": 0, "break_even": 0}

                by_band[band]["total"] += count
                if exit_type == "TP_HIT":
                    by_band[band]["tp_hit"] += count
                elif exit_type == "SL_HIT":
                    by_band[band]["sl_hit"] += count
                elif exit_type == "BREAK_EVEN":
                    by_band[band]["break_even"] += count
                else:
                    by_band[band]["manual_exit"] += count

            # Calculate rates
            for band in by_band:
                total = by_band[band]["total"]
                if total > 0:
                    by_band[band]["tp_hit_rate"] = round(by_band[band]["tp_hit"] / total * 100, 1)
                    by_band[band]["sl_hit_rate"] = round(by_band[band]["sl_hit"] / total * 100, 1)
                    by_band[band]["manual_exit_rate"] = round(by_band[band]["manual_exit"] / total * 100, 1)
                else:
                    by_band[band]["tp_hit_rate"] = 0
                    by_band[band]["sl_hit_rate"] = 0
                    by_band[band]["manual_exit_rate"] = 0

            return by_band

    def get_open_alerts_for_monitoring(self) -> list:
        """
        Get all alerts that should be monitored for SL/TP hits.

        Returns alerts where:
        - SL and TP are set (auto-calculated or custom)
        - Trade hasn't been recorded yet (no exit)
        - We haven't already notified about SL/TP hit
        """
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
            return [dict(row) for row in cursor.fetchall()]

    def check_and_record_tp_sl_hit(
        self,
        alert_id: int,
        current_price: float,
    ) -> tuple:
        """
        Check if an alert's current price touched SL or TP.

        Returns: (hit_type, price) where hit_type is "TP_HIT", "SL_HIT", or None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get alert details
            cursor.execute(
                """
                SELECT direction, entry_price, stop_loss, take_profit, timestamp
                FROM alerts
                WHERE id = ?
                """,
                (alert_id,),
            )
            result = cursor.fetchone()
            if not result:
                return None, None

            direction, entry_price, stop_loss, take_profit, entry_ts_str = result

            # Check if hit SL or TP
            tolerance = 0.1  # Allow 0.1 pt tolerance for price touches
            hit_type = None

            if direction == "LONG":
                if current_price >= (take_profit - tolerance):
                    hit_type = "TP_HIT"
                elif current_price <= (stop_loss + tolerance):
                    hit_type = "SL_HIT"
            else:  # SHORT
                if current_price <= (take_profit + tolerance):
                    hit_type = "TP_HIT"
                elif current_price >= (stop_loss - tolerance):
                    hit_type = "SL_HIT"

            if hit_type:
                # Auto-record the fill
                exit_type = self._determine_exit_type(
                    current_price, entry_price, direction, stop_loss, take_profit
                )

                exit_time = datetime.now()
                exit_ts = exit_time.timestamp()
                entry_ts = datetime.fromisoformat(entry_ts_str).timestamp()

                # Calculate P&L
                if direction == "LONG":
                    pnl = (current_price - entry_price) * 20
                    pnl_percent = ((current_price - entry_price) / entry_price) * 100
                else:
                    pnl = (entry_price - current_price) * 20
                    pnl_percent = ((entry_price - current_price) / entry_price) * 100

                hold_seconds = int(exit_ts - entry_ts)
                result_str = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BREAK_EVEN")

                # Insert trade record
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
                        alert_id,
                        entry_price,
                        entry_ts_str,
                        entry_ts,
                        current_price,
                        exit_time,
                        exit_ts,
                        round(pnl, 2),
                        round(pnl_percent, 2),
                        hold_seconds,
                        result_str,
                        f"Auto-recorded when {hit_type}",
                        exit_type,
                        stop_loss,
                        take_profit,
                    ),
                )

                # Mark as notified and record hit time
                cursor.execute(
                    """
                    UPDATE alerts
                    SET tp_sl_notified = 1, tp_sl_hit_at = ?, trade_status = 'FILLED'
                    WHERE id = ?
                    """,
                    (exit_time, alert_id),
                )

                conn.commit()

                log.info(
                    f"Auto-recorded: Alert {alert_id} {hit_type} @ {current_price:.2f} "
                    f"(SL: {stop_loss:.2f}, TP: {take_profit:.2f})"
                )

                return hit_type, current_price

            return None, None

    def record_market_close_exit(self, alert_id: int, exit_price: float) -> bool:
        """
        Record a market close exit (3:15 PM CT) for a pending alert.
        Used for futures trading where positions close at market hours.

        Returns: True if recorded successfully, False otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get alert details
            cursor.execute(
                """
                SELECT direction, current_price, timestamp
                FROM alerts
                WHERE id = ?
                """,
                (alert_id,),
            )
            result = cursor.fetchone()
            if not result:
                return False

            direction, entry_price, entry_ts_str = result

            # Calculate P&L
            if direction == "LONG":
                pnl = (exit_price - entry_price) * 20  # MNQ multiplier
                pnl_percent = ((exit_price - entry_price) / entry_price) * 100
            else:  # SHORT
                pnl = (entry_price - exit_price) * 20
                pnl_percent = ((entry_price - exit_price) / entry_price) * 100

            exit_time = datetime.now()
            exit_ts = exit_time.timestamp()
            entry_ts = datetime.fromisoformat(entry_ts_str).timestamp()
            hold_seconds = int(exit_ts - entry_ts)
            result_str = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BREAK_EVEN")

            try:
                # Insert trade record
                cursor.execute(
                    """
                    INSERT INTO trades (
                        alert_id, entry_price, entry_time, entry_ts,
                        exit_price, exit_time, exit_ts,
                        pnl, pnl_percent, hold_seconds, result, notes, exit_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        alert_id,
                        entry_price,
                        entry_ts_str,
                        entry_ts,
                        exit_price,
                        exit_time,
                        exit_ts,
                        round(pnl, 2),
                        round(pnl_percent, 2),
                        hold_seconds,
                        result_str,
                        "Market close (3:15 PM CT)",
                        "MARKET_CLOSE",
                    ),
                )

                # Mark alert as filled
                cursor.execute(
                    """
                    UPDATE alerts
                    SET exit_type = 'MARKET_CLOSE', trade_status = 'FILLED'
                    WHERE id = ?
                    """,
                    (alert_id,),
                )

                conn.commit()

                log.info(
                    f"Market close exit recorded: Alert {alert_id} "
                    f"entry={entry_price:.2f}, exit={exit_price:.2f}, P&L={pnl:.2f}"
                )
                return True

            except Exception as e:
                log.error(f"Failed to record market close exit for alert {alert_id}: {e}")
                return False

    def get_historical_stats(self, days: int = 14) -> dict:
        """
        Get performance statistics for the last N days.

        Used by agent to calibrate alert suggestions based on recent history.

        Returns:
        {
            "period_days": 14,
            "period_start": "2026-05-22",
            "period_end": "2026-06-05",
            "by_score_band": {
                "10+": {"total": 5, "tp_hit": 4, "sl_hit": 1, "tp_rate": 80.0},
                "8-10": {"total": 6, "tp_hit": 3, "sl_hit": 3, "tp_rate": 50.0},
                "5-8": {"total": 4, "tp_hit": 1, "sl_hit": 3, "tp_rate": 25.0},
                "<5": {"total": 2, "tp_hit": 0, "sl_hit": 2, "tp_rate": 0.0}
            },
            "by_direction": {
                "LONG": {"total": 10, "wins": 7, "win_rate": 70.0},
                "SHORT": {"total": 7, "wins": 2, "win_rate": 28.6}
            },
            "overall": {
                "total_trades": 17,
                "total_wins": 9,
                "win_rate": 52.9,
                "total_pnl": 4250.50,
                "avg_pnl": 250.03
            }
        }
        """
        from datetime import datetime, timedelta

        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get all trades in the period
            cursor.execute(
                """
                SELECT
                    t.*,
                    a.confluence_score,
                    a.direction
                FROM trades t
                JOIN alerts a ON t.alert_id = a.id
                WHERE a.date >= ? AND a.date <= ?
                ORDER BY a.date DESC
                """,
                (start_date.isoformat(), end_date.isoformat()),
            )

            trades = cursor.fetchall()

            if not trades:
                # No data for this period
                return {
                    "period_days": days,
                    "period_start": start_date.isoformat(),
                    "period_end": end_date.isoformat(),
                    "by_score_band": {},
                    "by_direction": {},
                    "overall": {
                        "total_trades": 0,
                        "total_wins": 0,
                        "win_rate": 0.0,
                        "total_pnl": 0.0,
                        "avg_pnl": 0.0,
                    },
                }

            # Process by score band
            by_score_band = {
                "10+": {"total": 0, "tp_hit": 0, "sl_hit": 0},
                "8-10": {"total": 0, "tp_hit": 0, "sl_hit": 0},
                "5-8": {"total": 0, "tp_hit": 0, "sl_hit": 0},
                "<5": {"total": 0, "tp_hit": 0, "sl_hit": 0},
            }

            # Process by direction
            by_direction = {
                "LONG": {"total": 0, "wins": 0},
                "SHORT": {"total": 0, "wins": 0},
            }

            total_trades = 0
            total_wins = 0
            total_pnl = 0.0

            for trade in trades:
                # trade format: (id, alert_id, entry_price, entry_time, entry_ts,
                #               exit_price, exit_time, exit_ts,
                #               pnl, pnl_percent, hold_seconds, result, notes,
                #               exit_type, stop_loss_price, take_profit_price,
                #               created_at, confluence_score, direction)

                confluence_score = trade[-2]
                direction = trade[-1]
                result = trade[11]
                exit_type = trade[13]
                pnl = trade[8]

                total_trades += 1
                total_pnl += pnl

                # Determine score band
                if confluence_score >= 10:
                    band = "10+"
                elif confluence_score >= 8:
                    band = "8-10"
                elif confluence_score >= 5:
                    band = "5-8"
                else:
                    band = "<5"

                # Count by band
                by_score_band[band]["total"] += 1
                if exit_type == "TP_HIT":
                    by_score_band[band]["tp_hit"] += 1
                elif exit_type == "SL_HIT":
                    by_score_band[band]["sl_hit"] += 1

                # Count by direction
                by_direction[direction]["total"] += 1
                if result == "WIN":
                    by_direction[direction]["wins"] += 1
                    total_wins += 1

            # Calculate rates
            for band in by_score_band:
                total = by_score_band[band]["total"]
                if total > 0:
                    tp_rate = (
                        by_score_band[band]["tp_hit"] / total * 100
                    )
                    by_score_band[band]["tp_rate"] = round(tp_rate, 1)
                else:
                    by_score_band[band]["tp_rate"] = 0.0

            for direction in by_direction:
                total = by_direction[direction]["total"]
                if total > 0:
                    win_rate = (
                        by_direction[direction]["wins"] / total * 100
                    )
                    by_direction[direction]["win_rate"] = round(win_rate, 1)
                else:
                    by_direction[direction]["win_rate"] = 0.0

            # Overall stats
            overall_win_rate = (
                (total_wins / total_trades * 100) if total_trades > 0 else 0
            )
            avg_pnl = (total_pnl / total_trades) if total_trades > 0 else 0

            return {
                "period_days": days,
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "by_score_band": by_score_band,
                "by_direction": by_direction,
                "overall": {
                    "total_trades": total_trades,
                    "total_wins": total_wins,
                    "win_rate": round(overall_win_rate, 1),
                    "total_pnl": round(total_pnl, 2),
                    "avg_pnl": round(avg_pnl, 2),
                },
            }

    def get_setup_stats(self, date_str: str) -> dict:
        """
        Analyze best/worst setups by confluence score band and direction.

        Returns: {
            "by_direction": {
                "LONG": {"total": 4, "won": 3, "win_rate": 75.0, "total_pnl": 500},
                "SHORT": {"total": 4, "won": 2, "win_rate": 50.0, "total_pnl": 250}
            },
            "by_score_band": {
                "10+": {"total": 2, "won": 2, "win_rate": 100.0},
                "8-10": {"total": 4, "won": 2, "win_rate": 50.0},
                "5-8": {"total": 2, "won": 1, "win_rate": 50.0}
            }
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # By direction
            cursor.execute(
                """
                SELECT
                    a.direction,
                    COUNT(*) as total,
                    SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as wins,
                    ROUND(SUM(t.pnl), 2) as pnl
                FROM alerts a
                LEFT JOIN trades t ON a.id = t.alert_id
                WHERE a.date = ?
                GROUP BY a.direction
                """,
                (date_str,),
            )

            by_direction = {}
            for direction, total, wins, pnl in cursor.fetchall():
                wins = wins or 0
                pnl = pnl or 0
                win_rate = (wins / total * 100) if total > 0 else 0
                by_direction[direction] = {
                    "total": total,
                    "won": wins,
                    "win_rate": round(win_rate, 1),
                    "total_pnl": pnl,
                }

            # By confluence score band
            cursor.execute(
                """
                SELECT
                    CASE
                        WHEN confluence_score >= 10 THEN '10+'
                        WHEN confluence_score >= 8 THEN '8-10'
                        WHEN confluence_score >= 5 THEN '5-8'
                        ELSE '<5'
                    END as band,
                    COUNT(*) as total,
                    SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as wins
                FROM alerts a
                LEFT JOIN trades t ON a.id = t.alert_id
                WHERE a.date = ?
                GROUP BY band
                """,
                (date_str,),
            )

            by_score_band = {}
            for band, total, wins in cursor.fetchall():
                wins = wins or 0
                win_rate = (wins / total * 100) if total > 0 else 0
                by_score_band[band] = {
                    "total": total,
                    "won": wins,
                    "win_rate": round(win_rate, 1),
                }

            return {
                "by_direction": by_direction,
                "by_score_band": by_score_band,
            }
