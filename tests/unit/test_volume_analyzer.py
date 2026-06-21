"""
Unit tests for Volume Analyzer
"""

import pytest
from src.analysis.volume_analyzer import (
    calculate_poc,
    detect_volume_spike,
    volume_confirmation,
)


class TestCalculatePOC:
    """Test POC (Point of Control) calculation"""

    def test_poc_simple(self):
        """Test basic POC calculation"""
        bars = [
            {"close": 100.0, "volume": 1000},
            {"close": 100.0, "volume": 2000},  # Most volume at 100.0
            {"close": 101.0, "volume": 500},
        ]

        poc = calculate_poc(bars, lookback=3)

        assert poc is not None
        assert poc == 100.0  # Highest volume level

    def test_poc_insufficient_lookback(self):
        """Test with insufficient bars for lookback"""
        bars = [
            {"close": 100.0, "volume": 1000},
            {"close": 101.0, "volume": 500},
        ]

        poc = calculate_poc(bars, lookback=10)

        assert poc is None

    def test_poc_empty(self):
        """Test with empty bars"""
        poc = calculate_poc([], lookback=5)
        assert poc is None

    def test_poc_rounding(self):
        """Test POC rounds to nearest 0.25"""
        bars = [
            {"close": 100.1, "volume": 1000},  # Rounds to 100.0
            {"close": 100.1, "volume": 2000},
            {"close": 101.3, "volume": 500},   # Rounds to 101.25
        ]

        poc = calculate_poc(bars, lookback=3)

        assert poc is not None
        # Should be 100.0 (2x volume at that tick)
        assert poc == 100.0


class TestDetectVolumeSpike:
    """Test volume spike detection"""

    def test_volume_spike_detected(self):
        """Test detection of volume spike"""
        bars = [
            {"volume": 1000},
            {"volume": 1000},
            {"volume": 1000},
            {"volume": 1000},
            {"volume": 1000},
            {"volume": 2000},  # 2x average = spike
        ]

        result = detect_volume_spike(bars, lookback=5, multiplier=1.5)

        assert result["spike_detected"] is True
        assert result["current_volume"] == 2000
        assert result["average_volume"] == 1000
        assert result["spike_ratio"] == 2.0
        assert result["confidence"] >= 70

    def test_no_volume_spike(self):
        """Test when no spike exists"""
        bars = [
            {"volume": 1000},
            {"volume": 1000},
            {"volume": 1000},
            {"volume": 1000},
            {"volume": 1000},
            {"volume": 1100},  # Only 10% above average
        ]

        result = detect_volume_spike(bars, lookback=5, multiplier=1.5)

        assert result["spike_detected"] is False
        assert result["spike_ratio"] < 1.5

    def test_volume_spike_confidence(self):
        """Test confidence scoring for different spike magnitudes"""
        bars_strong = [{"volume": 1000} for _ in range(5)] + [{"volume": 2500}]
        bars_moderate = [{"volume": 1000} for _ in range(5)] + [{"volume": 1800}]

        result_strong = detect_volume_spike(bars_strong, lookback=5, multiplier=1.5)
        result_moderate = detect_volume_spike(bars_moderate, lookback=5, multiplier=1.5)

        assert result_strong["confidence"] > result_moderate["confidence"]

    def test_insufficient_bars(self):
        """Test with insufficient bars"""
        bars = [{"volume": 1000}, {"volume": 1100}]

        result = detect_volume_spike(bars, lookback=5, multiplier=1.5)

        assert result["spike_detected"] is False

    def test_zero_average_volume(self):
        """Test with zero average volume"""
        bars = [{"volume": 0} for _ in range(6)]

        result = detect_volume_spike(bars, lookback=5, multiplier=1.5)

        assert result["spike_detected"] is False


class TestVolumeConfirmation:
    """Test volume confirmation"""

    def test_long_volume_confirms(self):
        """Test volume confirmation for LONG"""
        bars = [
            {"close": 100, "open": 101, "volume": 1000},  # Down
            {"close": 102, "open": 101, "volume": 1000},  # Down
            {"close": 102, "open": 101, "volume": 1000},  # Down
            {"close": 102, "open": 101, "volume": 1000},  # Down
            {"close": 102, "open": 101, "volume": 1000},  # Down
            {"close": 103, "open": 101, "volume": 1600},  # Up with strong volume (>1.5x)
        ]

        result = volume_confirmation(bars, direction="long")

        assert result["volume_confirms"] is True
        assert result["price_direction"] == "up"
        assert result["confirmation_strength"] == "strong"

    def test_short_volume_confirms(self):
        """Test volume confirmation for SHORT"""
        bars = [
            {"close": 102, "open": 101, "volume": 1000},  # Up
            {"close": 102, "open": 101, "volume": 1000},  # Up
            {"close": 102, "open": 101, "volume": 1000},  # Up
            {"close": 102, "open": 101, "volume": 1000},  # Up
            {"close": 102, "open": 101, "volume": 1000},  # Up
            {"close": 100, "open": 101, "volume": 1600},  # Down with strong volume (>1.5x)
        ]

        result = volume_confirmation(bars, direction="short")

        assert result["volume_confirms"] is True
        assert result["price_direction"] == "down"
        assert result["confirmation_strength"] == "strong"

    def test_volume_not_confirming(self):
        """Test when volume doesn't confirm price direction"""
        bars = [
            {"close": 101, "open": 101, "volume": 1000},
            {"close": 101, "open": 101, "volume": 1000},
            {"close": 101, "open": 101, "volume": 1000},
            {"close": 101, "open": 101, "volume": 1000},
            {"close": 101, "open": 101, "volume": 1000},
            {"close": 103, "open": 101, "volume": 800},  # Up but low volume
        ]

        result = volume_confirmation(bars, direction="long")

        assert result["volume_confirms"] is False
        assert result["confirmation_strength"] == "weak"

    def test_insufficient_bars(self):
        """Test with insufficient bars"""
        bars = [{"close": 102, "open": 101, "volume": 1000}]

        result = volume_confirmation(bars, direction="long")

        assert result["volume_confirms"] is False

    def test_empty_bars(self):
        """Test with empty bars"""
        result = volume_confirmation([], direction="long")

        assert result["volume_confirms"] is False
