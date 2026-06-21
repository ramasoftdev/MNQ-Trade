"""
Volume Analyzer - Volume, POC, and Volume Spike Detection
==========================================================
Analyzes volume data to identify:
- Point of Control (POC) - price level with most volume
- Volume spikes - unusual volume activity
- Volume confirmation - whether volume supports price action
"""

import logging
from typing import Optional, Dict, List
from collections import defaultdict

log = logging.getLogger("volume_analyzer")


def calculate_poc(bars: List[Dict], lookback: int = 24) -> Optional[float]:
    """
    Calculate Point of Control (POC) - the price level with most volume.

    Used as an institutional fair-value level.

    Args:
        bars: List of OHLCV bars
        lookback: Number of bars to analyze

    Returns:
        POC price level or None
    """
    if not bars or len(bars) < lookback:
        return None

    try:
        # Get recent bars
        recent_bars = bars[-lookback:]

        # Build price-volume map (round prices to nearest 0.25)
        price_volume = defaultdict(float)

        for bar in recent_bars:
            price = bar.get("close", 0)
            volume = bar.get("volume", 0)

            # Round price to nearest 0.25 (tick)
            rounded_price = round(price * 4) / 4

            price_volume[rounded_price] += volume

        if not price_volume:
            return None

        # Find price with highest volume
        poc = max(price_volume.items(), key=lambda x: x[1])[0]

        return round(poc, 2)

    except Exception as e:
        log.error(f"Error calculating POC: {e}")
        return None


def detect_volume_spike(
    bars: List[Dict],
    lookback: int = 5,
    multiplier: float = 1.5
) -> Dict:
    """
    Detect if current bar has volume spike.

    Args:
        bars: List of OHLCV bars
        lookback: Number of bars for average volume calculation
        multiplier: Volume spike threshold (e.g., 1.5x = 50% above average)

    Returns:
        {
            "spike_detected": bool,
            "current_volume": int,
            "average_volume": float,
            "spike_ratio": float,
            "confidence": 0-100
        }
    """
    if not bars or len(bars) < lookback + 1:
        return {
            "spike_detected": False,
            "current_volume": 0,
            "average_volume": 0,
            "spike_ratio": 0,
            "confidence": 0
        }

    try:
        # Current bar
        curr_bar = bars[-1]
        curr_volume = curr_bar.get("volume", 0)

        # Previous bars for average
        prev_bars = bars[-(lookback + 1):-1]
        prev_volumes = [bar.get("volume", 0) for bar in prev_bars]

        avg_volume = sum(prev_volumes) / len(prev_volumes) if prev_volumes else 0

        if avg_volume == 0:
            return {
                "spike_detected": False,
                "current_volume": curr_volume,
                "average_volume": 0,
                "spike_ratio": 0,
                "confidence": 0
            }

        spike_ratio = curr_volume / avg_volume

        spike_detected = spike_ratio >= multiplier

        # Confidence based on spike magnitude
        confidence = 0
        if spike_detected:
            if spike_ratio >= 2.0:
                confidence = 90  # Very strong spike
            elif spike_ratio >= 1.5:
                confidence = 70  # Moderate spike
            else:
                confidence = 50  # Just above threshold

        return {
            "spike_detected": spike_detected,
            "current_volume": int(curr_volume),
            "average_volume": round(avg_volume, 0),
            "spike_ratio": round(spike_ratio, 2),
            "confidence": confidence
        }

    except Exception as e:
        log.error(f"Error detecting volume spike: {e}")
        return {
            "spike_detected": False,
            "current_volume": 0,
            "average_volume": 0,
            "spike_ratio": 0,
            "confidence": 0
        }


def volume_confirmation(
    bars: List[Dict],
    direction: str = "long"
) -> Dict:
    """
    Check if current bar's volume confirms price direction.

    Args:
        bars: List of OHLCV bars
        direction: "long" (close up) or "short" (close down)

    Returns:
        {
            "volume_confirms": bool,
            "current_volume": int,
            "average_volume": float,
            "price_direction": "up" | "down" | "neutral",
            "confirmation_strength": "strong" | "medium" | "weak" | "none"
        }
    """
    if not bars or len(bars) < 2:
        return {
            "volume_confirms": False,
            "current_volume": 0,
            "average_volume": 0,
            "price_direction": "neutral",
            "confirmation_strength": "none"
        }

    try:
        curr_bar = bars[-1]
        prev_bar = bars[-2]

        curr_open = curr_bar.get("open", 0)
        curr_close = curr_bar.get("close", 0)
        curr_volume = curr_bar.get("volume", 0)

        # Get average volume (last 5 bars excluding current)
        prev_volumes = [bar.get("volume", 0) for bar in bars[-6:-1]]
        avg_volume = sum(prev_volumes) / len(prev_volumes) if prev_volumes else 0

        # Price direction
        if curr_close > curr_open:
            price_direction = "up"
        elif curr_close < curr_open:
            price_direction = "down"
        else:
            price_direction = "neutral"

        # Check if volume is above average
        volume_above_avg = curr_volume > avg_volume if avg_volume > 0 else False

        # Volume confirms if:
        # - LONG direction: price up AND volume above average
        # - SHORT direction: price down AND volume above average
        volume_confirms = False
        confirmation_strength = "none"

        if direction.lower() == "long":
            if price_direction == "up" and volume_above_avg:
                volume_confirms = True
                confirmation_strength = "strong" if curr_volume > avg_volume * 1.5 else "medium"
            elif price_direction == "up":
                confirmation_strength = "weak"

        elif direction.lower() == "short":
            if price_direction == "down" and volume_above_avg:
                volume_confirms = True
                confirmation_strength = "strong" if curr_volume > avg_volume * 1.5 else "medium"
            elif price_direction == "down":
                confirmation_strength = "weak"

        return {
            "volume_confirms": volume_confirms,
            "current_volume": int(curr_volume),
            "average_volume": round(avg_volume, 0),
            "price_direction": price_direction,
            "confirmation_strength": confirmation_strength
        }

    except Exception as e:
        log.error(f"Error checking volume confirmation: {e}")
        return {
            "volume_confirms": False,
            "current_volume": 0,
            "average_volume": 0,
            "price_direction": "neutral",
            "confirmation_strength": "none"
        }


def volume_profile_analysis(bars: List[Dict]) -> Dict:
    """
    Analyze volume profile to identify high/low volume nodes.

    Args:
        bars: List of OHLCV bars

    Returns:
        {
            "hvn": [high volume nodes],
            "lvn": [low volume nodes],
            "poc": point of control price
        }
    """
    if not bars:
        return {
            "hvn": [],
            "lvn": [],
            "poc": None
        }

    try:
        # Build price-volume map
        price_volume = defaultdict(float)

        for bar in bars:
            price = bar.get("close", 0)
            volume = bar.get("volume", 0)

            # Round to nearest 0.25
            rounded_price = round(price * 4) / 4
            price_volume[rounded_price] += volume

        if not price_volume:
            return {
                "hvn": [],
                "lvn": [],
                "poc": None
            }

        # Sort by volume
        sorted_pv = sorted(price_volume.items(), key=lambda x: x[1], reverse=True)

        # Find POC (highest volume)
        poc = sorted_pv[0][0] if sorted_pv else None

        # Find HVN (high volume nodes) - top 25%
        hvn_count = max(1, len(sorted_pv) // 4)
        hvn = [{"price": pv[0], "volume": int(pv[1])} for pv in sorted_pv[:hvn_count]]

        # Find LVN (low volume nodes) - bottom 25%
        lvn_count = max(1, len(sorted_pv) // 4)
        lvn = [{"price": pv[0], "volume": int(pv[1])} for pv in sorted_pv[-lvn_count:]]

        return {
            "hvn": hvn,
            "lvn": lvn,
            "poc": round(poc, 2) if poc else None
        }

    except Exception as e:
        log.error(f"Error analyzing volume profile: {e}")
        return {
            "hvn": [],
            "lvn": [],
            "poc": None
        }
