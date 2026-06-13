"""Trade business logic controller."""

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from src.models.alert import Alert
from src.models.trade import Trade
from src.database.alert_db import AlertDatabase
from src.database.trade_db import TradeDatabase

log = logging.getLogger("trade_controller")


class TradeController:
    """Handles trade recording, exit detection, and P&L calculation."""

    def __init__(self, alert_db: AlertDatabase = None, trade_db: TradeDatabase = None):
        self.alert_db = alert_db or AlertDatabase()
        self.trade_db = trade_db or TradeDatabase()

    def check_and_record_exit(self, alert_id: int, current_price: float) -> Optional[Trade]:
        """
        Check if alert's SL or TP was hit and record trade if so.

        Returns:
            Trade model if exit detected, None otherwise
        """
        alert = self.alert_db.get_by_id(alert_id)
        if not alert:
            log.warning(f"Alert {alert_id} not found")
            return None

        if not alert.has_targets():
            log.debug(f"Alert {alert_id} has no SL/TP set")
            return None

        # Determine if hit
        exit_type = self._determine_exit(alert, current_price)
        if not exit_type:
            return None

        # Calculate P&L
        pnl, pnl_percent, hold_seconds = self._calculate_pnl(alert, current_price)
        result = self._determine_result(pnl)

        # Create trade
        trade = Trade(
            alert_id=alert_id,
            entry_price=alert.entry_price,
            exit_price=current_price,
            direction=alert.direction,
            exit_type=exit_type,
            pnl=pnl,
            pnl_percent=pnl_percent,
            hold_seconds=hold_seconds,
            entry_time=alert.timestamp,
            exit_time=datetime.now(),
            stop_loss_price=alert.stop_loss,
            take_profit_price=alert.take_profit,
            result=result,
            notes=f"Auto-recorded when {exit_type}",
        )

        # Save trade
        trade.id = self.trade_db.save(trade)

        # Update alert status
        self.alert_db.update_status(alert_id, "FILLED", datetime.now())

        log.info(
            f"Trade recorded for Alert {alert_id}: {exit_type} @ {current_price:.2f} "
            f"(SL: {alert.stop_loss:.2f}, TP: {alert.take_profit:.2f}) | "
            f"P&L: ${pnl:.2f} ({pnl_percent:+.2f}%)"
        )

        return trade

    def _determine_exit(self, alert: Alert, current_price: float) -> Optional[str]:
        """Determine if SL or TP was hit."""
        tolerance = 0.25  # 0.25 point tolerance

        if alert.direction == "LONG":
            if current_price >= (alert.take_profit - tolerance):
                return "TP_HIT"
            elif current_price <= (alert.stop_loss + tolerance):
                return "SL_HIT"

        elif alert.direction == "SHORT":
            if current_price <= (alert.take_profit + tolerance):
                return "TP_HIT"
            elif current_price >= (alert.stop_loss - tolerance):
                return "SL_HIT"

        return None

    def _calculate_pnl(self, alert: Alert, exit_price: float) -> Tuple[float, float, int]:
        """
        Calculate P&L and hold time.

        Returns:
            (pnl, pnl_percent, hold_seconds)
        """
        # MNQ multiplier: $20 per point
        if alert.direction == "LONG":
            pnl = (exit_price - alert.entry_price) * 20
            pnl_percent = ((exit_price - alert.entry_price) / alert.entry_price) * 100
        else:  # SHORT
            pnl = (alert.entry_price - exit_price) * 20
            pnl_percent = ((alert.entry_price - exit_price) / alert.entry_price) * 100

        # Hold time
        now = datetime.now()
        if hasattr(alert.timestamp, "timestamp"):
            entry_ts = alert.timestamp.timestamp()
        else:
            entry_ts = datetime.fromisoformat(str(alert.timestamp)).timestamp()

        exit_ts = now.timestamp()
        hold_seconds = int(exit_ts - entry_ts)

        return round(pnl, 2), round(pnl_percent, 2), hold_seconds

    @staticmethod
    def _determine_result(pnl: float) -> str:
        """Determine trade result based on P&L."""
        if pnl > 0:
            return "WIN"
        elif pnl < 0:
            return "LOSS"
        else:
            return "BREAK_EVEN"

    def get_today_trades(self, date_str: str) -> List[Trade]:
        """Get all trades for today."""
        trades = self.trade_db.get_by_date(date_str)
        log.debug(f"Found {len(trades)} trades for {date_str}")
        return trades

    def get_trade(self, trade_id: int) -> Optional[Trade]:
        """Get trade by ID."""
        return self.trade_db.get_by_id(trade_id)

    def get_trade_by_alert(self, alert_id: int) -> Optional[Trade]:
        """Get trade by alert ID."""
        return self.trade_db.get_by_alert_id(alert_id)

    def get_all_trades(self) -> List[Trade]:
        """Get all trades."""
        return self.trade_db.get_all()

    def get_trades_by_exit_type(self, exit_type: str, date_str: str = None) -> List[Trade]:
        """Get trades by exit type (TP_HIT, SL_HIT, etc.)."""
        return self.trade_db.get_by_exit_type(exit_type, date_str)
