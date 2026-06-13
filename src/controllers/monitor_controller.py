"""Monitor controller for exit tracking."""

import logging
from typing import Optional

from src.models.trade import Trade
from src.controllers.trade_controller import TradeController

log = logging.getLogger("monitor_controller")


class MonitorController:
    """Orchestrates alert monitoring and exit detection."""

    def __init__(self, trade_controller: TradeController = None):
        self.trade_ctrl = trade_controller or TradeController()

    def check_pending_alerts(self, current_price: float) -> list:
        """
        Check all pending alerts and detect exits.

        Args:
            current_price: Current MNQ price

        Returns:
            List of Trade objects that were recorded (exits detected)
        """
        pending_alerts = self.trade_ctrl.alert_db.get_pending()

        if not pending_alerts:
            log.debug("No pending alerts to monitor")
            return []

        log.info(f"Monitoring {len(pending_alerts)} pending alerts @ {current_price:.2f}")

        recorded_trades = []

        for alert in pending_alerts:
            # Check if this alert's SL/TP was hit
            trade = self.trade_ctrl.check_and_record_exit(alert.id, current_price)

            if trade:
                recorded_trades.append(trade)
                log.info(
                    f"[MONITOR] Alert {alert.id} {trade.exit_type} @ {current_price:.2f} | "
                    f"P&L: ${trade.pnl:.2f} ({trade.pnl_percent:+.2f}%)"
                )

        return recorded_trades

    def get_trade_summary(self, trades: list) -> dict:
        """
        Get summary statistics for recorded trades.

        Args:
            trades: List of Trade objects

        Returns:
            Dictionary with summary stats
        """
        if not trades:
            return {
                "total": 0,
                "tp_hits": 0,
                "sl_hits": 0,
                "total_pnl": 0,
                "avg_pnl": 0,
            }

        tp_hits = sum(1 for t in trades if t.exit_type == "TP_HIT")
        sl_hits = sum(1 for t in trades if t.exit_type == "SL_HIT")
        total_pnl = sum(t.pnl for t in trades)
        avg_pnl = total_pnl / len(trades) if trades else 0

        return {
            "total": len(trades),
            "tp_hits": tp_hits,
            "sl_hits": sl_hits,
            "tp_hit_rate": (tp_hits / len(trades) * 100) if trades else 0,
            "sl_hit_rate": (sl_hits / len(trades) * 100) if trades else 0,
            "total_pnl": round(total_pnl, 2),
            "avg_pnl": round(avg_pnl, 2),
        }
