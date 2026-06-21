"""
VWAP Analyzer - Detect price bounces off VWAP
==============================================
Identifies when price bounces off VWAP with volume confirmation.
Used as primary entry signal for the new system.
"""

import logging
from typing import Optional, Dict, List

log = logging.getLogger("vwap_analyzer")


def calculate_vwap(bars: List[Dict]) -> Optional[float]:
    """
    Calculate Volume Weighted Average Price (VWAP).

    VWAP = Sum(Price × Volume) / Sum(Volume)

    Args:
        bars: List of OHLCV bars

    Returns:
        VWAP value or None if insufficient data
    """
    if not bars or len(bars) < 2:
        return None

    try:
        cumulative_tp_volume = 0.0
        cumulative_volume = 0.0

        for bar in bars:
            typical_price = (bar.get("high", 0) + bar.get("low", 0) + bar.get("close", 0)) / 3
            volume = bar.get("volume", 0)

            cumulative_tp_volume += typical_price * volume
            cumulative_volume += volume

        if cumulative_volume == 0:
            return None

        vwap = cumulative_tp_volume / cumulative_volume
        return round(vwap, 2)

    except Exception as e:
        log.error(f"Error calculating VWAP: {e}")
        return None


def detect_vwap_bounce(
    bars: List[Dict],
    vwap: float,
    current_price: float,
    direction: str = "long"
) -> Dict:
    """
    Detect if price is bouncing off VWAP with volume confirmation.

    LONG bounce: Price touches/crosses below VWAP, then reverses up
    SHORT bounce: Price touches/crosses above VWAP, then reverses down

    Args:
        bars: List of OHLCV bars (at least last 3 bars)
        vwap: Current VWAP level
        current_price: Current price
        direction: "long" or "short"

    Returns:
        {
            "bounce_detected": bool,
            "bounce_type": "reversal" or "none",
            "distance_from_vwap": float,
            "volume_confirmation": bool,
            "reversal_candle": bool,
            "confidence": 0-100
        }
    """

    if not bars or len(bars) < 2:
        return {
            "bounce_detected": False,
            "bounce_type": "none",
            "distance_from_vwap": 0,
            "volume_confirmation": False,
            "reversal_candle": False,
            "confidence": 0
        }

    try:
        # Get last 3 bars for analysis
        prev_bar = bars[-2] if len(bars) >= 2 else bars[-1]
        curr_bar = bars[-1]

        prev_close = prev_bar.get("close", 0)
        curr_open = curr_bar.get("open", 0)
        curr_close = curr_bar.get("close", 0)
        curr_high = curr_bar.get("high", 0)
        curr_low = curr_bar.get("low", 0)
        curr_volume = curr_bar.get("volume", 0)

        # Calculate average volume (last 3 bars)
        volumes = [bar.get("volume", 0) for bar in bars[-3:]]
        avg_volume = sum(volumes) / len(volumes) if volumes else 0

        # Distance from VWAP
        distance = abs(current_price - vwap)

        # Volume confirmation (current bar > average)
        volume_spike = curr_volume > avg_volume * 1.2 if avg_volume > 0 else False

        bounce_detected = False
        bounce_type = "none"
        confidence = 0
        reversal_candle = False

        if direction.lower() == "long":
            # LONG bounce: Price dips below VWAP, reverses up

            # Check if previous bar touched/crossed below VWAP
            prev_touched_vwap = prev_bar.get("low", 0) <= vwap

            # Check if current bar reversed (open near low, close near high)
            body_size = abs(curr_close - curr_open)
            total_range = curr_high - curr_low
            reversal_candle = (
                total_range > 0 and
                body_size / total_range > 0.5 and  # Body is at least 50% of range
                curr_close > curr_open  # Close above open (bullish)
            )

            # Check if price bounced up from VWAP
            curr_above_vwap = current_price > vwap

            if prev_touched_vwap and curr_above_vwap and reversal_candle:
                bounce_detected = True
                bounce_type = "reversal"
                confidence = 75 if volume_spike else 60

        elif direction.lower() == "short":
            # SHORT bounce: Price rises above VWAP, reverses down

            # Check if previous bar touched/crossed above VWAP
            prev_touched_vwap = prev_bar.get("high", 0) >= vwap

            # Check if current bar reversed (open near high, close near low)
            body_size = abs(curr_close - curr_open)
            total_range = curr_high - curr_low
            reversal_candle = (
                total_range > 0 and
                body_size / total_range > 0.5 and  # Body is at least 50% of range
                curr_close < curr_open  # Close below open (bearish)
            )

            # Check if price bounced down from VWAP
            curr_below_vwap = current_price < vwap

            if prev_touched_vwap and curr_below_vwap and reversal_candle:
                bounce_detected = True
                bounce_type = "reversal"
                confidence = 75 if volume_spike else 60

        return {
            "bounce_detected": bounce_detected,
            "bounce_type": bounce_type,
            "distance_from_vwap": round(distance, 2),
            "volume_confirmation": volume_spike,
            "reversal_candle": reversal_candle,
            "confidence": confidence
        }

    except Exception as e:
        log.error(f"Error detecting VWAP bounce: {e}")
        return {
            "bounce_detected": False,
            "bounce_type": "none",
            "distance_from_vwap": 0,
            "volume_confirmation": False,
            "reversal_candle": False,
            "confidence": 0
        }


def vwap_support_resistance(
    vwap: float,
    current_price: float,
    tolerance: float = 5.0
) -> str:
    """
    Classify VWAP as support or resistance.

    Args:
        vwap: Current VWAP level
        current_price: Current price
        tolerance: Distance tolerance (pts)

    Returns:
        "support", "resistance", or "none"
    """
    distance = current_price - vwap

    if abs(distance) > tolerance:
        return "none"

    if distance > 0:
        return "support"  # Price above VWAP
    else:
        return "resistance"  # Price below VWAP
