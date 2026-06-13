"""Alert data model."""

from datetime import datetime
from typing import Optional


class Alert:
    """Represents a trading alert for a detected sweep."""

    def __init__(
        self,
        direction: str,
        entry_price: float,
        confluence_score: float,
        trigger_tf: str = "?",
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        probability: int = 0,
        assessment: str = "UNKNOWN",
        confidence: str = "unknown",
        reasoning: str = "",
        timestamp: Optional[datetime] = None,
        id: Optional[int] = None,
        # Condition flags
        sweep_confirmed: bool = False,
        reversal_candle: bool = False,
        near_poc: bool = False,
        vwap_confluence: bool = False,
        tf_1h_aligned: bool = False,
        tf_3plus_aligned: bool = False,
        rth_session: bool = False,
        # Market context
        base_score: int = 0,
        ext_score: int = 0,
        spy_magnet_score: float = 0,
        current_vwap: float = 0,
        current_poc: float = 0,
        spy_price: float = 0,
        # Trade status
        trade_status: str = "PENDING",
        taken: bool = False,
        tp_sl_notified: bool = False,
        tp_sl_hit_at: Optional[datetime] = None,
    ):
        self.id = id
        self.timestamp = timestamp or datetime.now()
        self.direction = direction.upper()
        self.entry_price = entry_price
        self.confluence_score = confluence_score
        self.trigger_tf = trigger_tf
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.probability = probability
        self.assessment = assessment
        self.confidence = confidence
        self.reasoning = reasoning
        self.trade_status = trade_status

        # Conditions
        self.sweep_confirmed = sweep_confirmed
        self.reversal_candle = reversal_candle
        self.near_poc = near_poc
        self.vwap_confluence = vwap_confluence
        self.tf_1h_aligned = tf_1h_aligned
        self.tf_3plus_aligned = tf_3plus_aligned
        self.rth_session = rth_session

        # Market context
        self.base_score = base_score
        self.ext_score = ext_score
        self.spy_magnet_score = spy_magnet_score
        self.current_vwap = current_vwap
        self.current_poc = current_poc
        self.spy_price = spy_price

        # Trade tracking
        self.taken = taken
        self.tp_sl_notified = tp_sl_notified
        self.tp_sl_hit_at = tp_sl_hit_at

    def is_valid(self) -> bool:
        """Validate alert data."""
        if self.direction not in ["LONG", "SHORT"]:
            return False
        if self.entry_price <= 0:
            return False
        if self.confluence_score < 0 or self.confluence_score > 15:
            return False
        return True

    def has_targets(self) -> bool:
        """Check if SL and TP are set."""
        return self.stop_loss is not None and self.take_profit is not None

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "confluence_score": self.confluence_score,
            "trigger_tf": self.trigger_tf,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "probability": self.probability,
            "assessment": self.assessment,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "trade_status": self.trade_status,
            "sweep_confirmed": self.sweep_confirmed,
            "reversal_candle": self.reversal_candle,
            "near_poc": self.near_poc,
            "vwap_confluence": self.vwap_confluence,
            "tf_1h_aligned": self.tf_1h_aligned,
            "tf_3plus_aligned": self.tf_3plus_aligned,
            "rth_session": self.rth_session,
            "base_score": self.base_score,
            "ext_score": self.ext_score,
            "spy_magnet_score": self.spy_magnet_score,
            "current_vwap": self.current_vwap,
            "current_poc": self.current_poc,
            "spy_price": self.spy_price,
            "taken": self.taken,
            "tp_sl_notified": self.tp_sl_notified,
            "tp_sl_hit_at": self.tp_sl_hit_at,
        }

    def __repr__(self) -> str:
        return (
            f"Alert(id={self.id}, direction={self.direction}, "
            f"entry={self.entry_price:.2f}, score={self.confluence_score}, "
            f"status={self.trade_status})"
        )
