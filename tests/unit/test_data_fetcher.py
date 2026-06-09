"""
Unit tests for data_fetcher.py
Covers: bar buffer logic, bar close detection, callback firing, ready check.
No real WebSocket or HTTP calls made.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from collections import deque
import pytz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Patch config before importing data_fetcher
with patch.dict("os.environ", {}):
    from src.data.data_fetcher import MultiTimeframeFetcher

TZ = pytz.utc


def make_bar(ts: datetime, close=20000.0):
    return {
        "timestamp": ts,
        "open":   close - 5,
        "high":   close + 10,
        "low":    close - 10,
        "close":  close,
        "volume": 1000,
    }


def ts(offset_minutes=0):
    base = datetime(2026, 6, 2, 14, 0, 0, tzinfo=TZ)
    return base + timedelta(minutes=offset_minutes)


# ─────────────────────────────────────────────
# MultiTimeframeFetcher — bar buffer logic
# ─────────────────────────────────────────────

class TestMultiTimeframeFetcher:

    def _make_fetcher(self):
        fetcher = MultiTimeframeFetcher()
        return fetcher

    def test_initial_buffers_empty(self):
        fetcher = self._make_fetcher()
        for tf in ["1h", "30m", "15m", "5m"]:
            assert len(fetcher.get_bars(tf)) == 0

    def test_is_ready_false_when_empty(self):
        fetcher = self._make_fetcher()
        assert fetcher.is_ready(min_bars=1) is False

    def test_update_bar_same_timestamp_updates_in_flight(self):
        """Two bars with same timestamp → only one committed, values updated."""
        fetcher = self._make_fetcher()
        bar1 = make_bar(ts(0), close=20000.0)
        bar2 = make_bar(ts(0), close=20010.0)  # same timestamp, higher close

        fetcher._update_bar("5m", bar1)
        fetcher._update_bar("5m", bar2)

        # Nothing committed yet — same timestamp
        assert len(fetcher.get_bars("5m")) == 0
        # Current bar has updated close
        assert fetcher._current["5m"]["close"] == 20010.0

    def test_update_bar_new_timestamp_commits_previous(self):
        """New bar timestamp → previous bar committed to buffer."""
        fetcher = self._make_fetcher()
        bar1 = make_bar(ts(0), close=20000.0)
        bar2 = make_bar(ts(5), close=20010.0)  # new timestamp

        fetcher._update_bar("5m", bar1)
        fetcher._update_bar("5m", bar2)

        # bar1 should now be in the buffer
        bars = fetcher.get_bars("5m")
        assert len(bars) == 1
        assert bars[0]["close"] == 20000.0

    def test_callback_fires_on_trigger_tf_bar_close(self):
        """Bar close on 15m or 5m should fire the registered callback."""
        fetcher = self._make_fetcher()
        callback = MagicMock()
        fetcher.set_bar_close_callback(callback)

        bar1 = make_bar(ts(0), close=20000.0)
        bar2 = make_bar(ts(5), close=20010.0)

        fetcher._update_bar("5m", bar1)
        fetcher._update_bar("5m", bar2)

        # Give background thread a moment
        import time
        time.sleep(0.1)

        callback.assert_called_once()
        call_args = callback.call_args
        assert call_args[0][0] == "5m"

    def test_callback_does_not_fire_on_non_trigger_tf(self):
        """Bar close on 1h should NOT fire callback."""
        fetcher = self._make_fetcher()
        callback = MagicMock()
        fetcher.set_bar_close_callback(callback)

        bar1 = make_bar(ts(0), close=20000.0)
        bar2 = make_bar(ts(60), close=20010.0)

        fetcher._update_bar("1h", bar1)
        fetcher._update_bar("1h", bar2)

        import time
        time.sleep(0.1)

        callback.assert_not_called()

    def test_is_ready_true_when_enough_bars(self):
        fetcher = self._make_fetcher()
        # Fill all 4 TFs with enough bars
        for tf in ["1h", "30m", "15m", "5m"]:
            prev = make_bar(ts(0), close=20000.0)
            fetcher._update_bar(tf, prev)
            for i in range(1, 25):
                bar = make_bar(ts(i * 5), close=20000.0 + i)
                fetcher._update_bar(tf, bar)

        assert fetcher.is_ready(min_bars=20) is True

    def test_is_ready_false_when_one_tf_short(self):
        fetcher = self._make_fetcher()
        # Fill 3 TFs fully
        for tf in ["30m", "15m", "5m"]:
            prev = make_bar(ts(0))
            fetcher._update_bar(tf, prev)
            for i in range(1, 25):
                fetcher._update_bar(tf, make_bar(ts(i * 5)))

        # Leave 1h with only 5 bars
        prev = make_bar(ts(0))
        fetcher._update_bar("1h", prev)
        for i in range(1, 6):
            fetcher._update_bar("1h", make_bar(ts(i * 60)))

        assert fetcher.is_ready(min_bars=20) is False

    def test_get_latest_price_returns_5m_close(self):
        fetcher = self._make_fetcher()
        bar = make_bar(ts(0), close=20500.0)
        fetcher._current["5m"] = bar
        assert fetcher.get_latest_price() == 20500.0

    def test_get_latest_price_falls_back_to_buffer(self):
        fetcher = self._make_fetcher()
        # No current bar, but buffer has one
        fetcher._buffers["5m"].append(make_bar(ts(0), close=20300.0))
        assert fetcher.get_latest_price() == 20300.0

    def test_get_latest_price_zero_when_no_data(self):
        fetcher = self._make_fetcher()
        assert fetcher.get_latest_price() == 0.0

    def test_get_all_bars_returns_all_tfs(self):
        fetcher = self._make_fetcher()
        all_bars = fetcher.get_all_bars()
        assert set(all_bars.keys()) == {"1h", "30m", "15m", "5m"}

    def test_callback_receives_bars_snapshot(self):
        """Callback should receive a list snapshot of the buffer."""
        fetcher = self._make_fetcher()
        received = {}

        def callback(tf, bars):
            received["tf"] = tf
            received["bars"] = bars

        fetcher.set_bar_close_callback(callback)

        fetcher._update_bar("5m", make_bar(ts(0), close=20000.0))
        fetcher._update_bar("5m", make_bar(ts(5), close=20010.0))

        import time
        time.sleep(0.1)

        assert received.get("tf") == "5m"
        assert isinstance(received.get("bars"), list)
