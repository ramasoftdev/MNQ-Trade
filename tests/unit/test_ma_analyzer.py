"""
Unit tests for MA Analyzer
"""

import pytest
from src.analysis.ma_analyzer import (
    calculate_sma,
    calculate_mas,
    check_ma_alignment,
    classify_ma_levels,
)


class TestCalculateSMA:
    """Test SMA calculation"""

    def test_sma_5_period(self):
        """Test 5-period SMA"""
        closes = [100, 101, 102, 103, 104, 105, 106]
        sma = calculate_sma(closes, 5)

        assert sma is not None
        assert sma == 104.0  # (102+103+104+105+106)/5

    def test_sma_insufficient_data(self):
        """Test SMA with insufficient data"""
        closes = [100, 101, 102]
        sma = calculate_sma(closes, 5)

        assert sma is None

    def test_sma_exact_period(self):
        """Test SMA with exact period length"""
        closes = [100, 101, 102, 103, 104]
        sma = calculate_sma(closes, 5)

        assert sma == 102.0

    def test_sma_empty(self):
        """Test SMA with empty data"""
        sma = calculate_sma([], 5)
        assert sma is None


class TestCalculateMAs:
    """Test multiple MA calculation"""

    def test_calculate_multiple_mas(self):
        """Test calculating multiple MAs at once"""
        bars = [
            {"close": 100},
            {"close": 101},
            {"close": 102},
            {"close": 103},
            {"close": 104},
            {"close": 105},
        ]

        mas = calculate_mas(bars, [5, 3])

        assert "ma5" in mas
        assert "ma3" in mas
        assert mas["ma5"] is not None
        assert mas["ma3"] is not None

    def test_calculate_mas_default_periods(self):
        """Test with default periods [5, 20, 50]"""
        bars = [{"close": float(i)} for i in range(100, 160)]

        mas = calculate_mas(bars)

        assert "ma5" in mas
        assert "ma20" in mas
        assert "ma50" in mas

    def test_calculate_mas_empty_bars(self):
        """Test with empty bars"""
        mas = calculate_mas([], [5, 20, 50])

        assert mas["ma5"] is None
        assert mas["ma20"] is None
        assert mas["ma50"] is None


class TestCheckMAAlignment:
    """Test MA alignment checking"""

    def test_bullish_alignment(self):
        """Test bullish alignment (MA5 > MA20 > MA50)"""
        result = check_ma_alignment(105, 102, 100)

        assert result["alignment"] == "bullish"
        assert result["strength"] in ["strong", "medium", "weak"]
        assert result["order"] == "5>20>50"

    def test_bearish_alignment(self):
        """Test bearish alignment (MA5 < MA20 < MA50)"""
        result = check_ma_alignment(100, 102, 105)

        assert result["alignment"] == "bearish"
        assert result["strength"] in ["strong", "medium", "weak"]
        assert result["order"] == "5<20<50"

    def test_mixed_no_alignment(self):
        """Test mixed (no alignment)"""
        result = check_ma_alignment(105, 100, 102)

        assert result["alignment"] == "none"
        assert result["order"] == "mixed"

    def test_none_values(self):
        """Test with None values"""
        result = check_ma_alignment(None, 102, 100)

        assert result["alignment"] == "none"

    def test_strong_bullish(self):
        """Test strong bullish alignment"""
        result = check_ma_alignment(110, 105, 100)  # Large distances

        assert result["alignment"] == "bullish"
        assert result["strength"] == "strong"

    def test_weak_bullish(self):
        """Test weak bullish alignment"""
        result = check_ma_alignment(101, 100.5, 100)  # Small distances

        assert result["alignment"] == "bullish"
        assert result["strength"] == "weak"


class TestClassifyMALevels:
    """Test MA level classification"""

    def test_support_levels(self):
        """Test classification of support levels"""
        current_price = 105.0
        ma5 = 100.0
        ma20 = 98.0
        ma50 = 95.0

        result = classify_ma_levels(current_price, ma5, ma20, ma50, tolerance=20.0)

        assert len(result["support_levels"]) > 0
        # All MAs below price should be support
        for level in result["support_levels"]:
            assert level["price"] < current_price

    def test_resistance_levels(self):
        """Test classification of resistance levels"""
        current_price = 95.0
        ma5 = 100.0
        ma20 = 102.0
        ma50 = 105.0

        result = classify_ma_levels(current_price, ma5, ma20, ma50, tolerance=20.0)

        assert len(result["resistance_levels"]) > 0
        # All MAs above price should be resistance
        for level in result["resistance_levels"]:
            assert level["price"] > current_price

    def test_nearest_ma_tracking(self):
        """Test nearest MA tracking"""
        current_price = 100.0
        ma5 = 99.0  # Closest
        ma20 = 105.0
        ma50 = 110.0

        result = classify_ma_levels(current_price, ma5, ma20, ma50, tolerance=20.0)

        assert result["nearest_ma"]["period"] == 5
        assert result["nearest_ma"]["distance"] == 1.0

    def test_outside_tolerance(self):
        """Test levels outside tolerance are not classified"""
        current_price = 100.0
        ma5 = 100.0
        ma20 = 120.0  # Way outside tolerance
        ma50 = 50.0   # Way outside tolerance
        tolerance = 10.0

        result = classify_ma_levels(current_price, ma5, ma20, ma50, tolerance=tolerance)

        # Only ma5 should be in classified levels (within tolerance)
        support_count = len(result["support_levels"])
        resistance_count = len(result["resistance_levels"])
        assert support_count + resistance_count <= 1  # Only ma5 if at all
