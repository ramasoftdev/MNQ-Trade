"""
Shared test fixtures — mock bar data used across all test files.
"""

from datetime import datetime, timezone, timedelta
import pytz

TZ = pytz.timezone("America/Chicago")


def make_bar(ts: datetime, open_=100.0, high=105.0, low=95.0, close=102.0, volume=1000):
    """Create a single OHLCV bar dict."""
    return {
        "timestamp": ts,
        "open":   open_,
        "high":   high,
        "low":    low,
        "close":  close,
        "volume": volume,
    }


def rth_ts(hour=10, minute=0, day_offset=0):
    """Return a datetime in RTH (10:00 CT by default)."""
    base = datetime(2026, 6, 2, hour, minute, 0, tzinfo=TZ)
    return base + timedelta(days=day_offset)


def globex_ts(hour=20, minute=0, day_offset=0):
    """Return a datetime in Globex session (20:00 CT by default)."""
    base = datetime(2026, 6, 1, hour, minute, 0, tzinfo=TZ)
    return base + timedelta(days=day_offset)


def make_rth_bars(n=50, base_price=20000.0, volume=1000):
    """Generate n RTH bars with incrementing timestamps."""
    bars = []
    for i in range(n):
        ts = rth_ts(hour=9, minute=30) + timedelta(minutes=5 * i)
        bars.append(make_bar(
            ts=ts,
            open_=base_price + i,
            high=base_price + i + 5,
            low=base_price + i - 5,
            close=base_price + i + 2,
            volume=volume,
        ))
    return bars


def make_globex_bars(n=50, base_price=20000.0, volume=800):
    """Generate n Globex bars with incrementing timestamps."""
    bars = []
    for i in range(n):
        ts = globex_ts(hour=18, minute=0) + timedelta(minutes=5 * i)
        bars.append(make_bar(
            ts=ts,
            open_=base_price + i,
            high=base_price + i + 4,
            low=base_price + i - 4,
            close=base_price + i + 1,
            volume=volume,
        ))
    return bars


def make_session_levels(highs_lows=None):
    """
    Generate session H/L levels.
    Default: 3 prior sessions.
    """
    if highs_lows is None:
        highs_lows = [
            ("2026-05-30", 20100.0, 19900.0),
            ("2026-05-29", 20200.0, 19800.0),
            ("2026-05-28", 20050.0, 19950.0),
        ]
    return [
        {"date": d, "high": h, "low": l}
        for d, h, l in highs_lows
    ]


def make_mtf_bars(n=50, base_price=20000.0):
    """Generate a full mtf_bars dict with all 4 timeframes."""
    return {
        "1h":  make_rth_bars(n=max(n // 5, 10), base_price=base_price),
        "30m": make_rth_bars(n=max(n // 2, 20), base_price=base_price),
        "15m": make_rth_bars(n=n, base_price=base_price),
        "5m":  make_rth_bars(n=n * 2, base_price=base_price),
    }
