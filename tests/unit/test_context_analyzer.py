"""
Unit tests for context_analyzer.py
Covers: sweep detection, EMA, trend, alignment, VWAP, POC, session levels.
No live data, no API calls.
"""

import sys
import os
import pytest
from datetime import datetime, timedelta
import pytz

# Add parent dir to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analysis.context_analyzer import (
    compute_ema,
    compute_tf_trend,
    count_tf_alignment,
    compute_vwap,
    detect_sweep,
    compute_session_levels,
    compute_volume_stats,
    is_rth,
    is_globex,
)
from tests.fixtures.fixtures import (
    make_bar, rth_ts, globex_ts,
    make_rth_bars, make_globex_bars, make_session_levels,
)

TZ = pytz.timezone("America/Chicago")


# ─────────────────────────────────────────────
# is_rth / is_globex
# ─────────────────────────────────────────────

class TestSessionDetection:

    def test_rth_during_regular_hours(self):
        ts = rth_ts(hour=10, minute=30)
        assert is_rth(ts) is True

    def test_rth_at_open(self):
        ts = rth_ts(hour=9, minute=30)
        assert is_rth(ts) is True

    def test_not_rth_before_open(self):
        ts = rth_ts(hour=9, minute=0)
        assert is_rth(ts) is False

    def test_not_rth_after_close(self):
        ts = rth_ts(hour=16, minute=1)
        assert is_rth(ts) is False

    def test_globex_evening(self):
        ts = globex_ts(hour=20, minute=0)
        assert is_globex(ts) is True

    def test_not_globex_saturday(self):
        # June 6 2026 is a Saturday
        ts = datetime(2026, 6, 6, 20, 0, 0, tzinfo=TZ)
        assert is_globex(ts) is False


# ─────────────────────────────────────────────
# compute_ema
# ─────────────────────────────────────────────

class TestComputeEma:

    def test_single_value(self):
        result = compute_ema([100.0], period=1)
        assert result == pytest.approx(100.0)

    def test_all_same_values(self):
        values = [50.0] * 20
        result = compute_ema(values, period=10)
        assert result == pytest.approx(50.0, abs=0.01)

    def test_rising_values_ema_lags_price(self):
        values = list(range(1, 21))  # 1..20
        result = compute_ema(values, period=10)
        # EMA should be below last value (lags on the way up)
        assert result < values[-1]

    def test_fewer_bars_than_period(self):
        values = [100.0, 102.0, 104.0]
        result = compute_ema(values, period=10)
        # Should use available bars, not crash
        assert result > 0

    def test_empty_list(self):
        result = compute_ema([], period=10)
        assert result == 0.0


# ─────────────────────────────────────────────
# compute_tf_trend
# ─────────────────────────────────────────────

class TestComputeTfTrend:

    def _make_trending_bars(self, direction="bull", n=60):
        bars = []
        for i in range(n):
            ts = rth_ts(hour=9, minute=30) + timedelta(minutes=5 * i)
            price = 20000 + (i * 2 if direction == "bull" else -i * 2)
            bars.append(make_bar(ts=ts, close=price, high=price + 5, low=price - 5))
        return bars

    def test_bull_trend(self):
        bars = self._make_trending_bars("bull", n=60)
        result = compute_tf_trend(bars, "5m")
        assert result["trend"] == "bull"

    def test_bear_trend(self):
        bars = self._make_trending_bars("bear", n=60)
        result = compute_tf_trend(bars, "5m")
        assert result["trend"] == "bear"

    def test_insufficient_bars_returns_unknown(self):
        bars = make_rth_bars(n=5)
        result = compute_tf_trend(bars, "5m")
        assert result["trend"] == "unknown"

    def test_returns_required_keys(self):
        bars = make_rth_bars(n=60)
        result = compute_tf_trend(bars, "5m")
        assert "trend" in result
        assert "ema" in result
        assert "close" in result


# ─────────────────────────────────────────────
# count_tf_alignment
# ─────────────────────────────────────────────

class TestCountTfAlignment:

    def _make_trends(self, tf_trends: dict):
        """Build a trends dict from {tf: 'bull'|'bear'|'unknown'}."""
        return {
            tf: {"trend": t, "ema": 20000.0, "close": 20010.0}
            for tf, t in tf_trends.items()
        }

    def test_all_aligned_short(self):
        trends = self._make_trends({"1h": "bear", "30m": "bear", "15m": "bear", "5m": "bear"})
        result = count_tf_alignment(trends, "short")
        assert result["aligned"] == 4

    def test_all_aligned_long(self):
        trends = self._make_trends({"1h": "bull", "30m": "bull", "15m": "bull", "5m": "bull"})
        result = count_tf_alignment(trends, "long")
        assert result["aligned"] == 4

    def test_partial_alignment(self):
        trends = self._make_trends({"1h": "bear", "30m": "bear", "15m": "bull", "5m": "bull"})
        result = count_tf_alignment(trends, "short")
        assert result["aligned"] == 2

    def test_unknown_tf_excluded(self):
        trends = self._make_trends({"1h": "bear", "30m": "unknown", "15m": "bear", "5m": "bear"})
        result = count_tf_alignment(trends, "short")
        # unknown is excluded from total
        assert result["total"] == 3
        assert result["aligned"] == 3

    def test_detail_dict_correct(self):
        trends = self._make_trends({"1h": "bear", "30m": "bull", "15m": "bear", "5m": "bear"})
        result = count_tf_alignment(trends, "short")
        assert result["detail"]["1h"] is True
        assert result["detail"]["30m"] is False


# ─────────────────────────────────────────────
# detect_sweep
# ─────────────────────────────────────────────

class TestDetectSweep:

    def test_short_sweep_detected(self):
        """Bar wicks above session high and closes back below — short sweep."""
        levels = make_session_levels([("2026-05-30", 20100.0, 19900.0)])
        bars = make_rth_bars(n=10, base_price=20050.0)
        # Inject a sweep bar: wick above 20100, close below
        bars[-1] = make_bar(
            ts=rth_ts(hour=10, minute=30),
            high=20110.0,   # above session high 20100
            low=20040.0,
            close=20080.0,  # closes back below 20100
        )
        result = detect_sweep(bars, levels, "15m")
        assert result is not None
        assert result["direction"] == "short"
        assert result["level_price"] == 20100.0

    def test_long_sweep_detected(self):
        """Bar wicks below session low and closes back above — long sweep."""
        levels = make_session_levels([("2026-05-30", 20100.0, 19900.0)])
        bars = make_rth_bars(n=10, base_price=19950.0)
        bars[-1] = make_bar(
            ts=rth_ts(hour=10, minute=30),
            high=19980.0,
            low=19880.0,    # below session low 19900
            close=19920.0,  # closes back above 19900
        )
        result = detect_sweep(bars, levels, "15m")
        assert result is not None
        assert result["direction"] == "long"
        assert result["level_price"] == 19900.0

    def test_no_sweep_when_close_stays_above(self):
        """Bar wicks above high but closes above too — not a sweep."""
        levels = make_session_levels([("2026-05-30", 20100.0, 19900.0)])
        bars = make_rth_bars(n=10, base_price=20050.0)
        bars[-1] = make_bar(
            ts=rth_ts(hour=10, minute=30),
            high=20110.0,
            low=20050.0,
            close=20105.0,  # closes ABOVE the level — no rejection
        )
        result = detect_sweep(bars, levels, "15m")
        assert result is None

    def test_no_sweep_when_price_doesnt_reach_level(self):
        """Bar doesn't reach the session high — no sweep."""
        levels = make_session_levels([("2026-05-30", 20100.0, 19900.0)])
        bars = make_rth_bars(n=10, base_price=19950.0)
        result = detect_sweep(bars, levels, "15m")
        assert result is None

    def test_no_sweep_with_empty_levels(self):
        bars = make_rth_bars(n=10)
        result = detect_sweep(bars, [], "15m")
        assert result is None

    def test_no_sweep_with_insufficient_bars(self):
        levels = make_session_levels()
        bars = make_rth_bars(n=2)
        result = detect_sweep(bars, levels, "15m")
        assert result is None

    def test_sweep_returns_correct_keys(self):
        levels = make_session_levels([("2026-05-30", 20100.0, 19900.0)])
        bars = make_rth_bars(n=10, base_price=20050.0)
        bars[-1] = make_bar(
            ts=rth_ts(hour=10, minute=30),
            high=20110.0,
            low=20040.0,
            close=20080.0,
        )
        result = detect_sweep(bars, levels, "15m")
        for key in ["direction", "level_type", "level_price", "level_date",
                    "close_price", "sweep_size", "trigger_tf"]:
            assert key in result

    def test_sweep_size_calculated_correctly(self):
        levels = make_session_levels([("2026-05-30", 20100.0, 19900.0)])
        bars = make_rth_bars(n=10, base_price=20050.0)
        bars[-1] = make_bar(
            ts=rth_ts(hour=10, minute=30),
            high=20115.0,   # 15 pts above session high
            low=20040.0,
            close=20080.0,
        )
        result = detect_sweep(bars, levels, "15m")
        assert result["sweep_size"] == pytest.approx(15.0)


# ─────────────────────────────────────────────
# compute_vwap
# ─────────────────────────────────────────────

class TestComputeVwap:

    def test_vwap_with_rth_bars(self):
        """VWAP uses today's RTH bars — patch 'today' to match fixture date."""
        from unittest.mock import patch
        import context_analyzer as ca
        bars = make_rth_bars(n=20, base_price=20000.0)
        # Fixture bars are dated 2026-06-02; patch get_rth_session_date to return that
        with patch.object(ca, "get_rth_session_date", return_value="2026-06-02"):
            vwap = compute_vwap(bars)
        assert 19000 < vwap < 21000

    def test_vwap_zero_when_no_rth_bars(self):
        bars = make_globex_bars(n=20)
        vwap = compute_vwap(bars)
        assert vwap == 0.0

    def test_vwap_single_bar(self):
        """VWAP of one RTH bar = typical price (H+L+C)/3."""
        from unittest.mock import patch
        import context_analyzer as ca
        ts = rth_ts(hour=10, minute=0)
        bars = [make_bar(ts=ts, high=110.0, low=90.0, close=100.0, volume=500)]
        with patch.object(ca, "get_rth_session_date", return_value="2026-06-02"):
            vwap = compute_vwap(bars)
        # typical price = (110 + 90 + 100) / 3 = 100
        assert vwap == pytest.approx(100.0)


# ─────────────────────────────────────────────
# compute_volume_stats
# ─────────────────────────────────────────────

class TestComputeVolumeStats:

    def test_spike_detected_when_volume_high(self):
        bars = make_rth_bars(n=25, volume=1000)
        # Make last bar have very high volume
        bars[-1]["volume"] = 5000
        stats = compute_volume_stats(bars)
        assert stats["spike"] is True
        assert stats["ratio"] > 1.5

    def test_no_spike_normal_volume(self):
        bars = make_rth_bars(n=25, volume=1000)
        stats = compute_volume_stats(bars)
        assert stats["spike"] is False
        assert stats["ratio"] == pytest.approx(1.0, abs=0.1)

    def test_insufficient_bars_returns_defaults(self):
        bars = make_rth_bars(n=5)
        stats = compute_volume_stats(bars)
        assert stats["ratio"] == 1.0
        assert stats["spike"] is False


# ─────────────────────────────────────────────
# compute_session_levels
# ─────────────────────────────────────────────

class TestComputeSessionLevels:

    def test_returns_list_of_sessions(self):
        bars = make_globex_bars(n=100, base_price=20000.0)
        levels = compute_session_levels(bars)
        assert isinstance(levels, list)

    def test_each_level_has_required_keys(self):
        bars = make_globex_bars(n=100, base_price=20000.0)
        levels = compute_session_levels(bars)
        for level in levels:
            assert "date" in level
            assert "high" in level
            assert "low" in level

    def test_high_greater_than_low(self):
        bars = make_globex_bars(n=100, base_price=20000.0)
        levels = compute_session_levels(bars)
        for level in levels:
            assert level["high"] >= level["low"]

    def test_empty_bars_returns_empty(self):
        levels = compute_session_levels([])
        assert levels == []
