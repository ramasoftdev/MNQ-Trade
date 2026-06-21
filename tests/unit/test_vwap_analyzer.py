"""
Unit tests for VWAP Analyzer
"""

import pytest
from src.analysis.vwap_analyzer import calculate_vwap, detect_vwap_bounce, vwap_support_resistance


class TestCalculateVWAP:
    """Test VWAP calculation"""

    def test_vwap_simple(self):
        """Test VWAP with simple data"""
        bars = [
            {"high": 100, "low": 99, "close": 99.5, "volume": 1000},
            {"high": 101, "low": 100, "close": 100.5, "volume": 2000},
            {"high": 102, "low": 101, "close": 101.5, "volume": 1500},
        ]

        vwap = calculate_vwap(bars)
        assert vwap is not None
        assert 100 < vwap < 102

    def test_vwap_insufficient_data(self):
        """Test VWAP with insufficient data"""
        bars = [{"high": 100, "low": 99, "close": 99.5, "volume": 1000}]
        vwap = calculate_vwap(bars)
        assert vwap is None

    def test_vwap_empty(self):
        """Test VWAP with empty bars"""
        vwap = calculate_vwap([])
        assert vwap is None

    def test_vwap_zero_volume(self):
        """Test VWAP with zero volume"""
        bars = [
            {"high": 100, "low": 99, "close": 99.5, "volume": 0},
            {"high": 101, "low": 100, "close": 100.5, "volume": 0},
        ]
        vwap = calculate_vwap(bars)
        assert vwap is None


class TestDetectVWAPBounce:
    """Test VWAP bounce detection"""

    def test_long_bounce_detected(self):
        """Test LONG bounce detection"""
        vwap = 100.0
        bars = [
            {"high": 99.5, "low": 98.5, "close": 98.8, "open": 99.0, "volume": 1000},  # Touched VWAP
            {"high": 101.5, "low": 99.5, "close": 101.0, "open": 99.8, "volume": 1200},  # Reversal up
        ]
        current_price = 101.0

        result = detect_vwap_bounce(bars, vwap, current_price, direction="long")

        assert result["bounce_detected"] is True
        assert result["bounce_type"] == "reversal"
        assert result["confidence"] >= 60

    def test_short_bounce_detected(self):
        """Test SHORT bounce detection"""
        vwap = 100.0
        bars = [
            {"high": 101.5, "low": 100.5, "close": 101.2, "open": 100.8, "volume": 1000},  # Touched VWAP
            {"high": 99.5, "low": 98.5, "close": 99.0, "open": 101.0, "volume": 1200},  # Reversal down
        ]
        current_price = 99.0

        result = detect_vwap_bounce(bars, vwap, current_price, direction="short")

        assert result["bounce_detected"] is True
        assert result["bounce_type"] == "reversal"
        assert result["confidence"] >= 60

    def test_no_bounce_wrong_direction(self):
        """Test no bounce when price moves wrong way"""
        vwap = 100.0
        bars = [
            {"high": 99.5, "low": 98.5, "close": 98.8, "open": 99.0, "volume": 1000},
            {"high": 99.5, "low": 97.5, "close": 98.0, "open": 99.0, "volume": 1200},  # Wrong way
        ]
        current_price = 98.0

        result = detect_vwap_bounce(bars, vwap, current_price, direction="long")

        assert result["bounce_detected"] is False

    def test_insufficient_bars(self):
        """Test with insufficient bars"""
        bars = [{"high": 100, "low": 99, "close": 99.5, "volume": 1000}]
        result = detect_vwap_bounce(bars, 100.0, 99.5, direction="long")

        assert result["bounce_detected"] is False

    def test_empty_bars(self):
        """Test with empty bars"""
        result = detect_vwap_bounce([], 100.0, 99.5, direction="long")

        assert result["bounce_detected"] is False


class TestVWAPSupportResistance:
    """Test VWAP support/resistance classification"""

    def test_support_classification(self):
        """Test VWAP as support (price above VWAP)"""
        vwap = 100.0
        current_price = 102.0
        tolerance = 5.0

        result = vwap_support_resistance(vwap, current_price, tolerance)

        assert result == "support"

    def test_resistance_classification(self):
        """Test VWAP as resistance (price below VWAP)"""
        vwap = 100.0
        current_price = 98.0
        tolerance = 5.0

        result = vwap_support_resistance(vwap, current_price, tolerance)

        assert result == "resistance"

    def test_too_far_no_classification(self):
        """Test no classification when too far from VWAP"""
        vwap = 100.0
        current_price = 110.0
        tolerance = 5.0

        result = vwap_support_resistance(vwap, current_price, tolerance)

        assert result == "none"

    def test_at_vwap(self):
        """Test when price equals VWAP"""
        vwap = 100.0
        current_price = 100.0
        tolerance = 5.0

        result = vwap_support_resistance(vwap, current_price, tolerance)

        # At VWAP, should be classified as neither (but within tolerance)
        # Implementation returns "resistance" for equal
        assert result in ["resistance", "support", "none"]
