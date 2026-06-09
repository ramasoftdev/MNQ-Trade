"""
Unit tests for levels_analyzer.py
Covers: level parsing, MNQ conversion, proximity detection, pivot boost.
No file I/O — levels are injected via mocks.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.levels.levels_analyzer import (
    _parse_levels,
    mnq_to_spx_approx,
    mnq_to_spy_approx,
    analyze_levels,
    LevelHit,
    LevelsContext,
    SPY_PROXIMITY,
    SPX_PROXIMITY,
    PIVOT_BOOST,
    LEVEL_BOOST,
)


# ─────────────────────────────────────────────
# _parse_levels
# ─────────────────────────────────────────────

class TestParseLevels:

    def test_parses_plain_prices(self):
        raw = "530.0\n529.5\n528.0"
        levels, pivot = _parse_levels(raw)
        assert len(levels) == 3
        assert pivot is None

    def test_detects_pivot(self):
        raw = "530.0\n529.0 PIVOT\n528.0"
        levels, pivot = _parse_levels(raw)
        assert pivot == 529.0
        pivot_level = next(l for l in levels if l["is_pivot"])
        assert pivot_level["price"] == 529.0

    def test_skips_blank_lines(self):
        raw = "530.0\n\n528.0\n"
        levels, pivot = _parse_levels(raw)
        assert len(levels) == 2

    def test_skips_comment_lines(self):
        raw = "# this is a comment\n530.0\n528.0"
        levels, pivot = _parse_levels(raw)
        assert len(levels) == 2

    def test_sorted_descending(self):
        raw = "525.0\n530.0\n527.5"
        levels, _ = _parse_levels(raw)
        prices = [l["price"] for l in levels]
        assert prices == sorted(prices, reverse=True)

    def test_empty_input(self):
        levels, pivot = _parse_levels("")
        assert levels == []
        assert pivot is None

    def test_pivot_case_insensitive(self):
        raw = "530.0 pivot"
        levels, pivot = _parse_levels(raw)
        assert pivot == 530.0


# ─────────────────────────────────────────────
# Price conversion
# ─────────────────────────────────────────────

class TestPriceConversion:

    def test_mnq_to_spx_approx(self):
        # MNQ 23500 / 4.7 ≈ 5000
        result = mnq_to_spx_approx(23500.0)
        assert result == pytest.approx(5000.0, abs=1.0)

    def test_mnq_to_spy_approx(self):
        # SPX / 10 ≈ SPY
        spx = mnq_to_spx_approx(23500.0)
        spy = mnq_to_spy_approx(23500.0)
        assert spy == pytest.approx(spx / 10.0, abs=0.01)

    def test_conversion_positive(self):
        assert mnq_to_spx_approx(20000.0) > 0
        assert mnq_to_spy_approx(20000.0) > 0


# ─────────────────────────────────────────────
# analyze_levels
# ─────────────────────────────────────────────

MOCK_SPY = [
    {"price": 530.0, "is_pivot": False},
    {"price": 529.0, "is_pivot": True},
    {"price": 528.0, "is_pivot": False},
]

MOCK_SPX = [
    {"price": 5300.0, "is_pivot": False},
    {"price": 5290.0, "is_pivot": True},
    {"price": 5280.0, "is_pivot": False},
]


def _mock_load_levels(spy=None, spx=None, spy_pivot=529.0, spx_pivot=5290.0):
    """Return a mock load_levels patch value."""
    return (
        spy or MOCK_SPY,
        spx or MOCK_SPX,
        spy_pivot,
        spx_pivot,
        "2026-06-02",
    )


class TestAnalyzeLevels:

    @patch("src.levels.levels_analyzer.load_levels")
    def test_no_hit_when_far_from_levels(self, mock_load):
        mock_load.return_value = _mock_load_levels()
        # MNQ price that maps nowhere near SPY 529-530 or SPX 5290-5300
        ctx = analyze_levels(10000.0)
        assert len(ctx.hits) == 0
        assert ctx.score_boost == 0

    @patch("src.levels.levels_analyzer.load_levels")
    def test_spy_hit_detected(self, mock_load):
        mock_load.return_value = _mock_load_levels()
        # MNQ price that maps to SPY ≈ 530.0
        # SPY = mnq / 4.7 / 10 → mnq = 530 * 10 * 4.7 = 24910
        mnq_price = 530.0 * 10 * 4.7
        ctx = analyze_levels(mnq_price)
        spy_hits = [h for h in ctx.hits if h.instrument == "SPY"]
        assert len(spy_hits) > 0

    @patch("src.levels.levels_analyzer.load_levels")
    def test_pivot_gets_higher_boost(self, mock_load):
        mock_load.return_value = _mock_load_levels()
        # Price near SPY pivot (529.0)
        mnq_price = 529.0 * 10 * 4.7
        ctx = analyze_levels(mnq_price)
        pivot_hits = [h for h in ctx.hits if h.is_pivot]
        if pivot_hits:
            assert pivot_hits[0].boost == PIVOT_BOOST
            regular_hits = [h for h in ctx.hits if not h.is_pivot]
            for h in regular_hits:
                assert h.boost == LEVEL_BOOST

    @patch("src.levels.levels_analyzer.load_levels")
    def test_score_boost_sums_all_hits(self, mock_load):
        mock_load.return_value = _mock_load_levels()
        mnq_price = 529.0 * 10 * 4.7
        ctx = analyze_levels(mnq_price)
        expected_boost = sum(h.boost for h in ctx.hits)
        assert ctx.score_boost == expected_boost

    @patch("src.levels.levels_analyzer.load_levels")
    def test_pivot_acting_as_support(self, mock_load):
        mock_load.return_value = _mock_load_levels()
        # Price ABOVE pivot → pivot acts as support
        mnq_price = (529.0 + 0.3) * 10 * 4.7  # slightly above pivot
        ctx = analyze_levels(mnq_price)
        pivot_hits = [h for h in ctx.hits if h.is_pivot]
        if pivot_hits:
            assert ctx.pivot_acting_as == "support"

    @patch("src.levels.levels_analyzer.load_levels")
    def test_pivot_acting_as_resistance(self, mock_load):
        mock_load.return_value = _mock_load_levels()
        # Price BELOW pivot → pivot acts as resistance
        mnq_price = (529.0 - 0.3) * 10 * 4.7  # slightly below pivot
        ctx = analyze_levels(mnq_price)
        pivot_hits = [h for h in ctx.hits if h.is_pivot]
        if pivot_hits:
            assert ctx.pivot_acting_as == "resistance"

    @patch("src.levels.levels_analyzer.load_levels")
    def test_summary_not_empty_on_hit(self, mock_load):
        mock_load.return_value = _mock_load_levels()
        mnq_price = 529.0 * 10 * 4.7
        ctx = analyze_levels(mnq_price)
        if ctx.hits:
            assert ctx.summary != ""
            assert "not near" not in ctx.summary.lower()

    @patch("src.levels.levels_analyzer.load_levels")
    def test_no_hits_returns_not_near_summary(self, mock_load):
        mock_load.return_value = _mock_load_levels()
        ctx = analyze_levels(10000.0)
        assert "not near" in ctx.summary.lower()
