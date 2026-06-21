"""
VWAP/POC System Validator
=========================
Backtests the new system against historical data.
Replays bars and shows what alerts would have fired.

Usage:
  python src/core/validator_vwap_poc.py

Output:
  - Alerts triggered
  - Confluence scores
  - Claude probability
  - Performance stats
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pytz

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.data.config import (
    CONFLUENCE_THRESHOLD, CONFLUENCE_MAX,
    VOLUME_SPIKE_MULTIPLIER, MA_PERIODS,
)
from src.analysis.vwap_analyzer import calculate_vwap, detect_vwap_bounce
from src.analysis.ma_analyzer import calculate_mas, check_ma_alignment, analyze_daily_mas
from src.analysis.volume_analyzer import detect_volume_spike, calculate_poc
from src.analysis.probability_engine import get_probability

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("validator")

TZ = pytz.timezone("America/Chicago")


def check_vwap_bounce_signal_backtest(bars_5m, bars_15m, bars_1d, bar_index):
    """
    Backtest version of alert detection.
    Returns alert if triggered, None otherwise.
    """
    if not bars_5m or not bars_15m or not bars_1d:
        return None

    if bar_index >= len(bars_5m):
        return None

    # Current and previous bars for 5m
    curr_bar = bars_5m[bar_index]
    current_price = curr_bar.get("close", 0)

    # Use bars up to current index
    bars_5m_slice = bars_5m[:bar_index + 1]
    bars_15m_slice = bars_15m[:bar_index + 1]
    bars_1d_slice = bars_1d[:bar_index + 1]

    # Calculate VWAP
    vwap_5m = calculate_vwap(bars_5m_slice)
    vwap_15m = calculate_vwap(bars_15m_slice)

    if vwap_5m is None or vwap_15m is None:
        return None

    # Detect bounce
    bounce_long = detect_vwap_bounce(bars_5m_slice, vwap_5m, current_price, direction="long")
    bounce_short = detect_vwap_bounce(bars_5m_slice, vwap_5m, current_price, direction="short")

    bounce_detected = False
    direction = None

    if bounce_long.get("bounce_detected"):
        bounce_detected = True
        direction = "LONG"
    elif bounce_short.get("bounce_detected"):
        bounce_detected = True
        direction = "SHORT"

    if not bounce_detected:
        return None

    # Check 15m MA alignment
    mas_15m = calculate_mas(bars_15m_slice, MA_PERIODS["15m"])
    ma5_15m = mas_15m.get("ma5")
    ma20_15m = mas_15m.get("ma20")
    ma50_15m = mas_15m.get("ma50")

    if any(ma is None for ma in [ma5_15m, ma20_15m, ma50_15m]):
        return None

    alignment_info = check_ma_alignment(ma5_15m, ma20_15m, ma50_15m)
    alignment = alignment_info.get("alignment", "none")

    # Confirm direction
    if direction == "LONG" and alignment != "bullish":
        return None
    if direction == "SHORT" and alignment != "bearish":
        return None

    # Volume check
    volume_info = detect_volume_spike(bars_5m_slice, lookback=5, multiplier=VOLUME_SPIKE_MULTIPLIER)
    volume_spike = volume_info.get("spike_detected", False)
    volume_score = 2 if volume_spike else 1

    # Confluence score
    confluence_score = 3 + volume_score + 2  # VWAP + volume + MA

    poc_5m = calculate_poc(bars_5m_slice, lookback=24)
    if poc_5m and abs(current_price - poc_5m) < 5:
        confluence_score += 1

    if abs(current_price - ma5_15m) < 5:
        confluence_score += 1

    if confluence_score < CONFLUENCE_THRESHOLD:
        return None

    # Daily context
    mas_1d = calculate_mas(bars_1d_slice, MA_PERIODS["1d"])
    daily_ma5 = mas_1d.get("ma5")
    daily_ma50 = mas_1d.get("ma50")

    # TP/SL
    if direction == "LONG":
        stop_loss = daily_ma50 - 5 if daily_ma50 else current_price - 15
        take_profit = daily_ma5 + 5 if daily_ma5 else current_price + 20
    else:
        stop_loss = daily_ma50 + 5 if daily_ma50 else current_price + 15
        take_profit = daily_ma5 - 5 if daily_ma5 else current_price - 20

    return {
        "index": bar_index,
        "timestamp": curr_bar.get("time", ""),
        "direction": direction,
        "entry_price": current_price,
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "confluence_score": confluence_score,
        "vwap_5m": vwap_5m,
        "vwap_15m": vwap_15m,
        "volume_ratio": volume_info.get("spike_ratio", 0),
    }


def validate_with_claude(alert):
    """Get Claude's probability assessment for an alert."""
    try:
        prob_input = {
            "direction": alert["direction"],
            "entry_price": alert["entry_price"],
            "stop_loss": alert["stop_loss"],
            "take_profit": alert["take_profit"],
            "confluence_score": alert["confluence_score"],
            "timestamp": alert["timestamp"],
        }

        prob = get_probability(prob_input)
        return prob
    except Exception as e:
        log.error(f"Claude call failed: {e}")
        return {
            "probability": 0,
            "confidence": "error",
            "assessment": "error",
            "reasoning": str(e),
        }


def load_historical_bars():
    """
    Load historical bars from data fetcher.
    For now, returns empty - would need to integrate with data_fetcher.
    """
    # This is a placeholder - in real testing, you'd load actual bars
    # For now, we show the structure
    return None, None, None


def run_validation_report():
    """Run validation and generate report."""
    print("\n" + "=" * 80)
    print("VWAP/POC SYSTEM VALIDATOR")
    print("=" * 80)

    print("\n[TEST] Phase 3 - Testing Framework")
    print("-" * 80)

    print("\n[OK] Configuration loaded:")
    print(f"  - Confluence threshold: {CONFLUENCE_THRESHOLD}/{CONFLUENCE_MAX} pts")
    print(f"  - Volume spike multiplier: {VOLUME_SPIKE_MULTIPLIER}x")
    print(f"  - MA periods: {MA_PERIODS}")

    print("\n[PENDING] Status: Waiting for historical data")
    print("-" * 80)

    print("""
TO COMPLETE PHASE 3 TESTING:

Option A: Load Yesterday's Live Data
  1. Export 5m, 15m, 1d bars from your broker
  2. Save to: data/historical/mnq_2026-06-15.json
  3. Re-run validator to backtest

Option B: Manual Testing
  1. Start the live agent: python src/core/agent_vwap_poc.py
  2. Monitor next 5m bars in real time
  3. Record alerts and confluence scores
  4. Compare with Claude probability

Option C: Simulate Known Setup
  If you have the image data from yesterday, we can manually calculate
  what alerts would have fired at specific times.

NEXT STEPS:
-----------
1. Which option would you like to use?
2. Once data is available, validator will show:
   - All alerts triggered
   - Confluence score breakdown
   - Claude probability for each
   - Entry/SL/TP levels
   - Performance metrics
""")

    print("=" * 80)


def main():
    """Main validation entry point."""
    run_validation_report()


if __name__ == "__main__":
    main()
