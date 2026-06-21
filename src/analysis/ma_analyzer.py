"""
MA Analyzer - Moving Average Analysis
======================================
Calculates and analyzes 5m, 15m, and 1d moving averages.
Used for trend confirmation and support/resistance classification.
"""

import logging
from typing import Optional, Dict, List

log = logging.getLogger("ma_analyzer")


def calculate_sma(closes: List[float], period: int) -> Optional[float]:
    """
    Calculate Simple Moving Average.

    SMA = Sum(closes) / period

    Args:
        closes: List of closing prices
        period: SMA period (5, 20, 50, etc)

    Returns:
        SMA value or None if insufficient data
    """
    if not closes or len(closes) < period:
        return None

    try:
        sma = sum(closes[-period:]) / period
        return round(sma, 2)
    except Exception as e:
        log.error(f"Error calculating SMA({period}): {e}")
        return None


def calculate_mas(bars: List[Dict], periods: List[int] = None) -> Dict[str, Optional[float]]:
    """
    Calculate multiple SMAs for a timeframe.

    Args:
        bars: List of OHLCV bars
        periods: List of periods to calculate (default: [5, 20, 50])

    Returns:
        {
            "ma5": value,
            "ma20": value,
            "ma50": value,
            ...
        }
    """
    if periods is None:
        periods = [5, 20, 50]

    if not bars:
        return {f"ma{p}": None for p in periods}

    try:
        closes = [bar.get("close", 0) for bar in bars]
        result = {}

        for period in periods:
            sma = calculate_sma(closes, period)
            result[f"ma{period}"] = sma

        return result

    except Exception as e:
        log.error(f"Error calculating MAs: {e}")
        return {f"ma{p}": None for p in periods}


def check_ma_alignment(
    ma5: Optional[float],
    ma20: Optional[float],
    ma50: Optional[float]
) -> Dict:
    """
    Check if MAs are aligned (bullish or bearish).

    Bullish: MA5 > MA20 > MA50
    Bearish: MA5 < MA20 < MA50
    None: MAs not aligned

    Args:
        ma5: 5-period MA
        ma20: 20-period MA
        ma50: 50-period MA

    Returns:
        {
            "alignment": "bullish" | "bearish" | "none",
            "strength": "strong" | "medium" | "weak" | "none",
            "order": "5>20>50" | "5<20<50" | "mixed"
        }
    """
    if any(ma is None for ma in [ma5, ma20, ma50]):
        return {
            "alignment": "none",
            "strength": "none",
            "order": "unknown"
        }

    try:
        # Check bullish alignment
        if ma5 > ma20 > ma50:
            distance = min(ma5 - ma20, ma20 - ma50)
            strength = "strong" if distance > 2 else "medium" if distance > 0.5 else "weak"
            return {
                "alignment": "bullish",
                "strength": strength,
                "order": "5>20>50"
            }

        # Check bearish alignment
        elif ma5 < ma20 < ma50:
            distance = min(ma20 - ma5, ma50 - ma20)
            strength = "strong" if distance > 2 else "medium" if distance > 0.5 else "weak"
            return {
                "alignment": "bearish",
                "strength": strength,
                "order": "5<20<50"
            }

        # Mixed (not aligned)
        else:
            return {
                "alignment": "none",
                "strength": "weak",
                "order": "mixed"
            }

    except Exception as e:
        log.error(f"Error checking MA alignment: {e}")
        return {
            "alignment": "none",
            "strength": "none",
            "order": "unknown"
        }


def classify_ma_levels(
    current_price: float,
    ma5: Optional[float],
    ma20: Optional[float],
    ma50: Optional[float],
    tolerance: float = 15.0
) -> Dict:
    """
    Classify MAs as support, resistance, or key levels.

    Args:
        current_price: Current price
        ma5, ma20, ma50: MA values
        tolerance: Distance tolerance (pts) to count as "near"

    Returns:
        {
            "support_levels": [...],
            "resistance_levels": [...],
            "key_levels": [...],
            "nearest_ma": {"period": 5, "price": X, "distance": Y}
        }
    """
    support_levels = []
    resistance_levels = []
    key_levels = []
    nearest_ma = None
    min_distance = float("inf")

    mas = {
        5: ma5,
        20: ma20,
        50: ma50
    }

    try:
        for period, ma_price in mas.items():
            if ma_price is None:
                continue

            distance = abs(current_price - ma_price)

            # Track nearest MA
            if distance < min_distance:
                min_distance = distance
                nearest_ma = {
                    "period": period,
                    "price": ma_price,
                    "distance": round(distance, 2)
                }

            # Only classify if within tolerance
            if distance > tolerance:
                continue

            # Classify
            if period == 50:
                classification = "MAJOR"
            elif period == 20:
                classification = "KEY"
            else:
                classification = "minor"

            if current_price > ma_price:
                support_levels.append({
                    "period": period,
                    "price": ma_price,
                    "distance": round(distance, 2),
                    "classification": classification
                })
            else:
                resistance_levels.append({
                    "period": period,
                    "price": ma_price,
                    "distance": round(distance, 2),
                    "classification": classification
                })

            key_levels.append({
                "period": period,
                "price": ma_price,
                "type": "support" if current_price > ma_price else "resistance",
                "classification": classification
            })

        return {
            "support_levels": support_levels,
            "resistance_levels": resistance_levels,
            "key_levels": key_levels,
            "nearest_ma": nearest_ma or {}
        }

    except Exception as e:
        log.error(f"Error classifying MA levels: {e}")
        return {
            "support_levels": [],
            "resistance_levels": [],
            "key_levels": [],
            "nearest_ma": {}
        }


def analyze_daily_mas(
    daily_bars: List[Dict],
    current_price: float
) -> Dict:
    """
    Comprehensive analysis of daily MAs for macro context.

    Args:
        daily_bars: List of daily OHLCV bars
        current_price: Current price

    Returns:
        {
            "daily_mas": {"ma5": X, "ma20": Y, "ma50": Z},
            "daily_alignment": "bullish" | "bearish" | "none",
            "daily_trend_strength": "strong" | "medium" | "weak",
            "support_levels": [...],
            "resistance_levels": [...],
            "price_position": "above_all" | "between_5_20" | "between_20_50" | "below_all",
            "macro_context": "STRONG_UPTREND" | "WEAK_UPTREND" | etc
        }
    """
    if not daily_bars:
        return {
            "daily_mas": {},
            "daily_alignment": "none",
            "daily_trend_strength": "none",
            "support_levels": [],
            "resistance_levels": [],
            "price_position": "unknown",
            "macro_context": "UNKNOWN"
        }

    try:
        # Calculate daily MAs
        daily_mas = calculate_mas(daily_bars, [5, 20, 50])
        ma5 = daily_mas.get("ma5")
        ma20 = daily_mas.get("ma20")
        ma50 = daily_mas.get("ma50")

        # Check alignment
        alignment_info = check_ma_alignment(ma5, ma20, ma50)
        alignment = alignment_info.get("alignment", "none")
        strength = alignment_info.get("strength", "none")

        # Classify levels
        levels_info = classify_ma_levels(current_price, ma5, ma20, ma50, tolerance=20.0)

        # Determine price position relative to MAs
        price_position = "unknown"
        if all(ma is not None for ma in [ma5, ma20, ma50]):
            if current_price > ma5:
                price_position = "above_all"
            elif current_price > ma20:
                price_position = "between_5_20"
            elif current_price > ma50:
                price_position = "between_20_50"
            else:
                price_position = "below_all"

        # Macro context
        macro_context = "UNKNOWN"
        if alignment == "bullish":
            macro_context = f"STRONG_UPTREND" if strength == "strong" else "WEAK_UPTREND"
        elif alignment == "bearish":
            macro_context = f"STRONG_DOWNTREND" if strength == "strong" else "WEAK_DOWNTREND"
        else:
            macro_context = "RANGING"

        return {
            "daily_mas": daily_mas,
            "daily_alignment": alignment,
            "daily_trend_strength": strength,
            "support_levels": levels_info.get("support_levels", []),
            "resistance_levels": levels_info.get("resistance_levels", []),
            "price_position": price_position,
            "macro_context": macro_context
        }

    except Exception as e:
        log.error(f"Error analyzing daily MAs: {e}")
        return {
            "daily_mas": {},
            "daily_alignment": "none",
            "daily_trend_strength": "none",
            "support_levels": [],
            "resistance_levels": [],
            "price_position": "unknown",
            "macro_context": "ERROR"
        }
