"""Trade data model."""

from datetime import datetime
from typing import Optional


class Trade:
    """Represents a completed trade with entry/exit and P&L."""

    def __init__(
        self,
        alert_id: int,
        entry_price: float,
        exit_price: float,
        direction: str,
        exit_type: str,
        pnl: float,
        pnl_percent: float,
        hold_seconds: int,
        entry_time: Optional[datetime] = None,
        exit_time: Optional[datetime] = None,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        result: str = "UNKNOWN",
        notes: str = "",
        id: Optional[int] = None,
    ):
        self.id = id
        self.alert_id = alert_id
        self.entry_price = entry_price
        self.exit_price = exit_price
        self.direction = direction.upper()
        self.exit_type = exit_type  # TP_HIT, SL_HIT, MANUAL_EXIT, BREAK_EVEN, MARKET_CLOSE
        self.pnl = pnl
        self.pnl_percent = pnl_percent
        self.hold_seconds = hold_seconds
        self.result = result  # WIN, LOSS, BREAK_EVEN
        self.notes = notes
        self.entry_time = entry_time or datetime.now()
        self.exit_time = exit_time or datetime.now()
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price

    @property
    def is_win(self) -> bool:
        """Check if trade was profitable."""
        return self.pnl > 0

    @property
    def is_loss(self) -> bool:
        """Check if trade was a loss."""
        return self.pnl < 0

    @property
    def is_break_even(self) -> bool:
        """Check if trade broke even."""
        return abs(self.pnl) < 0.01  # Within $0.01

    def is_valid(self) -> bool:
        """Validate trade data."""
        if self.alert_id <= 0:
            return False
        if self.entry_price <= 0 or self.exit_price <= 0:
            return False
        if self.direction not in ["LONG", "SHORT"]:
            return False
        if self.exit_type not in ["TP_HIT", "SL_HIT", "MANUAL_EXIT", "BREAK_EVEN", "MARKET_CLOSE"]:
            return False
        if self.hold_seconds < 0:
            return False
        return True

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "alert_id": self.alert_id,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "direction": self.direction,
            "exit_type": self.exit_type,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "hold_seconds": self.hold_seconds,
            "result": self.result,
            "notes": self.notes,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
        }

    def __repr__(self) -> str:
        return (
            f"Trade(alert={self.alert_id}, dir={self.direction}, "
            f"entry={self.entry_price:.2f}, exit={self.exit_price:.2f}, "
            f"pnl=${self.pnl:.2f} ({self.pnl_percent:+.2f}%), "
            f"type={self.exit_type})"
        )
