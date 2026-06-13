"""
Component 3 — Multi-Timeframe Context Analyzer
================================================
Accepts a dict of bar lists (one per TF) and computes:
  - Trend / bias per timeframe
  - Sweep detection on trigger TFs (15m and 5m)
  - Timeframe alignment count
  - VWAP, POC, volume, session levels
  - Full context dict for Claude and Discord
"""

import math
import pytz
from datetime import datetime, timedelta
from collections import defaultdict
from src.data.config import (
    VOLUME_AVG_BARS, VOL_SPIKE_MULT, POC_PROXIMITY_PTS,
    VWAP_PROXIMITY_PTS, TICK_SIZE, TIMEZONE,
    RTH_START, RTH_END, GLOBEX_OPEN_HOUR, GLOBEX_CLOSE_HOUR,
    NUM_SESSIONS, POC_SESSIONS, SMA_PERIODS, MIN_TF_ALIGNMENT,
    TIMEFRAMES, DAILY_SMA_MAGNET_PROXIMITY,
)
from src.levels.levels_analyzer import analyze_levels, get_nearest_levels

TZ = pytz.timezone(TIMEZONE)
TF_LABEL = {"1d": "Daily", "15m": "15-Min", "5m": "5-Min"}


# ── Session helpers ───────────────────────────────────────

def is_rth(ts: datetime) -> bool:
    local = ts.astimezone(TZ)
    h, m  = local.hour, local.minute
    after  = h > RTH_START[0] or (h == RTH_START[0] and m >= RTH_START[1])
    before = h < RTH_END[0]   or (h == RTH_END[0]   and m == 0)
    return after and before


def is_globex(ts: datetime) -> bool:
    local = ts.astimezone(TZ)
    if local.hour == 16 and local.minute < 15:
        return False
    if local.weekday() == 5:
        return False
    if local.weekday() == 6 and local.hour < 17:
        return False
    return True


def get_globex_session_date(ts: datetime) -> str:
    local = ts.astimezone(TZ)
    if local.hour >= GLOBEX_OPEN_HOUR:
        session_day = local + timedelta(days=1)
    else:
        session_day = local
    return session_day.strftime("%Y-%m-%d")


def get_rth_session_date(ts: datetime) -> str:
    local = ts.astimezone(TZ)
    if local.hour < RTH_START[0] or (
        local.hour == RTH_START[0] and local.minute < RTH_START[1]
    ):
        local -= timedelta(days=1)
    return local.strftime("%Y-%m-%d")


# ── EMA / Trend ───────────────────────────────────────────

def compute_sma(values: list, period: int) -> float:
    """Compute Simple Moving Average."""
    if not values or len(values) < period:
        return 0.0
    return sum(values[-period:]) / period


def compute_sma_list(values: list, periods: list) -> dict:
    """
    Compute multiple SMAs at once.

    Args:
        values: List of prices
        periods: List of SMA periods (e.g., [5, 20, 50, 100, 200])

    Returns:
        {"sma_5": 123.45, "sma_20": 124.30, ...}
    """
    result = {}
    for period in periods:
        sma = compute_sma(values, period)
        result[f"sma_{period}"] = round(sma, 2) if sma > 0 else 0
    return result


def score_breakout_strength(distance: float) -> float:
    """
    Score SMA breakout strength based on distance.

    Args:
        distance: How far price is from the SMA (positive = above, negative = below)

    Returns:
        Score: 0.0-1.5 based on breakout strength
    """
    abs_dist = abs(distance)

    if abs_dist >= 10:
        return 1.5  # Strong breakout
    elif abs_dist >= 5:
        return 1.0  # Solid breakout
    elif abs_dist >= 1:
        return 0.5  # Just crossed
    else:
        return 0.0  # Too close to SMA


def detect_sma_breakouts(bars: list, smas: dict, direction: str) -> dict:
    """
    Detect bullish/bearish breakouts through SMA levels.

    Checks if price has broken above (for LONG) or below (for SHORT)
    moving averages with strength scoring.

    Args:
        bars: List of bar data
        smas: Dict of SMA values {"sma_5": X, "sma_20": Y, ...}
        direction: "long" or "short"

    Returns:
        {
            "breakout_score": 0.0-4.5,  # Sum of all SMA breakouts
            "breakouts": [
                {"period": 5, "sma_price": X, "distance": Y, "score": 1.0, "type": "bullish"},
                ...
            ]
        }
    """
    if not bars or not smas:
        return {
            "breakout_score": 0.0,
            "breakouts": [],
        }

    current_price = bars[-1]["close"] if bars else 0
    breakouts = []
    total_score = 0.0

    for sma_key, sma_price in smas.items():
        if sma_price <= 0:
            continue

        # Extract period from key (e.g., "sma_50" -> 50)
        try:
            period = int(sma_key.split("_")[1])
        except:
            continue

        distance = current_price - sma_price

        # For LONG: breakout above SMA is bullish
        # For SHORT: breakout below SMA is bearish
        if direction.lower() == "long":
            if distance > 0:  # Price above SMA (bullish)
                score = score_breakout_strength(distance)
                if score > 0:
                    breakouts.append({
                        "period": period,
                        "sma_price": round(sma_price, 2),
                        "distance": round(distance, 2),
                        "score": score,
                        "type": "bullish",
                    })
                    total_score += score
        else:  # SHORT
            if distance < 0:  # Price below SMA (bearish)
                score = score_breakout_strength(distance)
                if score > 0:
                    breakouts.append({
                        "period": period,
                        "sma_price": round(sma_price, 2),
                        "distance": round(distance, 2),
                        "score": score,
                        "type": "bearish",
                    })
                    total_score += score

    return {
        "breakout_score": round(total_score, 1),
        "breakouts": breakouts,
    }


def detect_sma_crosses(closes: list, periods: list = [5, 20, 50]) -> dict:
    """
    Detect golden cross (bullish) and death cross (bearish) signals.

    Golden Cross: Fast SMA > Medium/Slow SMA
    Death Cross: Fast SMA < Medium/Slow SMA

    Returns:
        {
            "golden_cross": bool,
            "death_cross": bool,
            "cross_type": "golden" | "death" | "none",
            "smas": {"sma_5": ..., "sma_20": ..., "sma_50": ...}
        }
    """
    if len(closes) < max(periods):
        return {
            "golden_cross": False,
            "death_cross": False,
            "cross_type": "none",
            "smas": {},
        }

    # Compute current SMAs
    smas = compute_sma_list(closes, periods)
    sma_fast = smas.get(f"sma_{periods[0]}", 0)
    sma_med = smas.get(f"sma_{periods[1]}", 0) if len(periods) > 1 else 0
    sma_slow = smas.get(f"sma_{periods[2]}", 0) if len(periods) > 2 else 0

    if sma_fast <= 0 or sma_med <= 0 or sma_slow <= 0:
        return {
            "golden_cross": False,
            "death_cross": False,
            "cross_type": "none",
            "smas": smas,
        }

    # Check for crosses
    golden_cross = sma_fast > sma_med and sma_med > sma_slow
    death_cross = sma_fast < sma_med and sma_med < sma_slow

    cross_type = "golden" if golden_cross else ("death" if death_cross else "none")

    return {
        "golden_cross": golden_cross,
        "death_cross": death_cross,
        "cross_type": cross_type,
        "smas": smas,
    }


def compute_tf_trend(bars: list, tf: str) -> dict:
    """
    Compute SMA-based trend for a single timeframe (15m, 5m).
    Includes cross detection and SMA positioning.
    Returns {
        "trend": "bull"|"bear"|"unknown",
        "cross_type": "golden"|"death"|"none",
        "sma_fast": float,
        "smas": {...},
        "close": float
    }
    """
    periods = SMA_PERIODS.get(tf, [5, 20, 50])
    if not periods:
        return {
            "trend": "unknown",
            "cross_type": "none",
            "sma_fast": 0.0,
            "smas": {},
            "close": 0.0,
        }

    closes = [b["close"] for b in bars if is_globex(b["timestamp"])]
    if len(closes) < 10:
        return {
            "trend": "unknown",
            "cross_type": "none",
            "sma_fast": 0.0,
            "smas": {},
            "close": 0.0,
        }

    # Detect crosses
    crosses = detect_sma_crosses(closes, periods)
    close = closes[-1]

    # Determine trend from crosses and price position
    if crosses["golden_cross"]:
        trend = "bull"
    elif crosses["death_cross"]:
        trend = "bear"
    else:
        # Default: check if price above fastest SMA
        sma_fast = crosses["smas"].get(f"sma_{periods[0]}", 0)
        trend = "bull" if close > sma_fast else "bear"

    return {
        "trend": trend,
        "cross_type": crosses["cross_type"],
        "sma_fast": round(crosses["smas"].get(f"sma_{periods[0]}", 0), 2),
        "smas": crosses["smas"],
        "close": round(close, 2),
    }


def compute_all_trends(mtf_bars: dict) -> dict:
    """Returns trend dict for all four timeframes."""
    return {tf: compute_tf_trend(mtf_bars[tf], tf) for tf in TIMEFRAMES}


def count_tf_alignment(trends: dict, direction: str) -> dict:
    """
    Count how many TFs agree with the trade direction.
    Returns {"aligned": int, "total": int, "detail": {tf: bool}}
    """
    expected = "bear" if direction == "short" else "bull"
    detail   = {
        tf: (info["trend"] == expected)
        for tf, info in trends.items()
        if info["trend"] != "unknown"
    }
    return {
        "aligned": sum(detail.values()),
        "total":   len(detail),
        "detail":  detail,
    }


# ── Intraday SMA Magnet Levels (15m, 5m) ──────────────
def compute_intraday_sma_levels(bars: list, current_price: float, tf: str = "15m", direction: str = "long") -> dict:
    """
    Compute 15m/5m SMA levels and score them as magnet support/resistance.
    Also detects golden/death crosses and SMA breakouts with strength scoring.

    Returns:
        {
            "smas": {"sma_5": ..., "sma_20": ..., "sma_50": ...},
            "magnet_score": 0.0-2.0,
            "breakout_score": 0.0-4.5,
            "nearest_sma": {"period": 5, "price": ..., "distance": ...},
            "hits": [...],
            "crosses": {"golden_cross": bool, "death_cross": bool, "cross_type": str},
            "breakouts": [...]  # Detected breakouts with strength
        }
    """
    from src.data.config import SMA_PERIODS, DAILY_SMA_MAGNET_PROXIMITY

    closes = [b["close"] for b in bars if bars]
    periods = SMA_PERIODS.get(tf, [5, 20, 50])

    if len(closes) < max(periods):
        return {
            "smas": {},
            "magnet_score": 0,
            "breakout_score": 0,
            "nearest_sma": None,
            "hits": [],
            "crosses": {
                "golden_cross": False,
                "death_cross": False,
                "cross_type": "none",
            },
            "breakouts": [],
        }

    # Compute SMAs and detect crosses
    smas = compute_sma_list(closes, periods)
    crosses = detect_sma_crosses(closes, periods)
    breakouts = detect_sma_breakouts(bars, smas, direction)

    # Find SMAs price is near (magnet levels)
    hits = []
    nearest_sma = None
    nearest_distance = float('inf')

    for period in periods:
        sma_price = smas.get(f"sma_{period}", 0)
        if sma_price <= 0:
            continue

        distance = abs(current_price - sma_price)

        # Track nearest
        if distance < nearest_distance:
            nearest_distance = distance
            nearest_sma = {"period": period, "price": sma_price, "distance": round(distance, 2)}

        # Record if within magnet proximity
        if distance <= DAILY_SMA_MAGNET_PROXIMITY:
            hits.append({
                "type": f"{tf}_sma",
                "period": period,
                "price": sma_price,
                "distance": round(distance, 2),
            })

    # Calculate magnet score
    magnet_score = 0.0
    for hit in hits:
        dist = hit["distance"]
        if dist < 3:
            magnet_score += 2.0
        elif dist < 7:
            magnet_score += 1.0
        elif dist <= DAILY_SMA_MAGNET_PROXIMITY:
            magnet_score += 0.5

    return {
        "smas": smas,
        "magnet_score": round(magnet_score, 1),
        "breakout_score": breakouts.get("breakout_score", 0),
        "nearest_sma": nearest_sma,
        "hits": hits,
        "crosses": crosses,
        "breakouts": breakouts.get("breakouts", []),
    }


# ── Daily SMA Magnet Levels ──────────────────────────────
def compute_daily_sma_levels(bars_1d: list, current_price: float, direction: str = "long") -> dict:
    """
    Compute daily SMAs and score them as magnet support/resistance levels.
    Also detects SMA breakouts with strength scoring.

    Returns:
        {
            "smas": {"sma_5": 100.0, "sma_20": 101.5, ...},
            "magnet_score": 0.0-2.0,
            "breakout_score": 0.0-7.5,
            "nearest_sma": {"period": 20, "price": 101.5, "distance": 0.5},
            "hits": [...],
            "breakouts": [...]  # Detected breakouts with strength
        }
    """
    from src.data.config import SMA_PERIODS, DAILY_SMA_MAGNET_PROXIMITY

    closes = [b["close"] for b in bars_1d if bars_1d]
    if len(closes) < 200:  # Need at least 200 bars for longest SMA
        return {
            "smas": {},
            "magnet_score": 0,
            "breakout_score": 0,
            "nearest_sma": None,
            "hits": [],
            "breakouts": [],
        }

    periods = SMA_PERIODS.get("1d", [5, 20, 50, 100, 200])
    smas = compute_sma_list(closes, periods)
    breakouts = detect_sma_breakouts(bars_1d, smas, direction)

    # Find SMAs price is near (magnet levels)
    hits = []
    nearest_sma = None
    nearest_distance = float('inf')

    for period in periods:
        sma_price = smas.get(f"sma_{period}", 0)
        if sma_price <= 0:
            continue

        distance = abs(current_price - sma_price)

        # Track nearest
        if distance < nearest_distance:
            nearest_distance = distance
            nearest_sma = {"period": period, "price": sma_price, "distance": round(distance, 2)}

        # Record if within magnet proximity
        if distance <= DAILY_SMA_MAGNET_PROXIMITY:
            hits.append({
                "type": "daily_sma",
                "period": period,
                "price": sma_price,
                "distance": round(distance, 2),
            })

    # Calculate magnet score (similar to SPY pivot scoring)
    magnet_score = 0.0
    for hit in hits:
        dist = hit["distance"]
        if dist < 3:  # Very close
            magnet_score += 2.0
        elif dist < 7:  # Close
            magnet_score += 1.0
        elif dist <= DAILY_SMA_MAGNET_PROXIMITY:  # Medium
            magnet_score += 0.5

    return {
        "smas": smas,
        "magnet_score": round(magnet_score, 1),
        "breakout_score": breakouts.get("breakout_score", 0),
        "nearest_sma": nearest_sma,
        "hits": hits,
        "breakouts": breakouts.get("breakouts", []),
    }


# ── VWAP ─────────────────────────────────────────────────

def compute_vwap(bars: list) -> float:
    """RTH-anchored VWAP using the most granular bars available."""
    cum_pv = cum_v = 0.0
    today  = get_rth_session_date(datetime.now(TZ))
    for bar in bars:
        if not is_rth(bar["timestamp"]):
            continue
        if get_rth_session_date(bar["timestamp"]) != today:
            continue
        tp      = (bar["high"] + bar["low"] + bar["close"]) / 3.0
        cum_pv += tp * bar["volume"]
        cum_v  += bar["volume"]
    return cum_pv / cum_v if cum_v > 0 else 0.0


# ── Volume Profile / POC ──────────────────────────────────

def round_tick(price: float) -> float:
    return round(round(price / TICK_SIZE) * TICK_SIZE, 10)


def compute_poc(bars: list, session_date: str) -> float:
    """POC for a single Globex session using full session bars."""
    profile: dict = defaultdict(float)
    for bar in bars:
        if not is_globex(bar["timestamp"]):
            continue
        if get_globex_session_date(bar["timestamp"]) != session_date:
            continue
        lo   = round_tick(bar["low"])
        hi   = round_tick(bar["high"])
        ticks = max(1, round((hi - lo) / TICK_SIZE) + 1)
        vpbt  = bar["volume"] / ticks
        p     = lo
        while p <= hi + 1e-9:
            profile[round_tick(p)] += vpbt
            p = round_tick(p + TICK_SIZE)
    return max(profile, key=lambda x: profile[x]) if profile else 0.0


def compute_session_pocs(bars: list) -> list:
    """POC list for last POC_SESSIONS completed Globex sessions."""
    today     = get_globex_session_date(datetime.now(TZ))
    all_dates = sorted(
        set(
            get_globex_session_date(b["timestamp"])
            for b in bars if is_globex(b["timestamp"])
        ),
        reverse=True,
    )
    completed = [d for d in all_dates if d != today]
    result    = []
    for d in completed[:POC_SESSIONS]:
        poc = compute_poc(bars, d)
        if poc > 0:
            result.append({"date": d, "poc": poc})
    return result


# ── Volume ────────────────────────────────────────────────

def compute_volume_stats(bars: list) -> dict:
    if len(bars) < VOLUME_AVG_BARS + 1:
        return {"avg": 0, "current": 0, "ratio": 1.0, "spike": False}
    recent = bars[-(VOLUME_AVG_BARS + 1):-1]
    avg    = sum(b["volume"] for b in recent) / len(recent)
    cur    = bars[-1]["volume"]
    ratio  = cur / avg if avg > 0 else 1.0
    return {
        "avg":     avg,
        "current": cur,
        "ratio":   round(ratio, 2),
        "spike":   ratio >= VOL_SPIKE_MULT,
    }


# ── Session H/L levels — built from 1H bars ──────────────

def compute_session_levels(bars_1h: list) -> list:
    """
    H/L for last NUM_SESSIONS completed full Globex sessions.
    Uses 1H bars — fewer data points, still captures real liquidity.
    """
    today    = get_globex_session_date(datetime.now(TZ))
    sessions = {}
    for bar in bars_1h:
        if not is_globex(bar["timestamp"]):
            continue
        sd = get_globex_session_date(bar["timestamp"])
        if sd not in sessions:
            sessions[sd] = {"high": bar["high"], "low": bar["low"]}
        else:
            sessions[sd]["high"] = max(sessions[sd]["high"], bar["high"])
            sessions[sd]["low"]  = min(sessions[sd]["low"],  bar["low"])

    completed = sorted([s for s in sessions if s != today], reverse=True)
    return [
        {"date": d, "high": sessions[d]["high"], "low": sessions[d]["low"]}
        for d in completed[:NUM_SESSIONS]
    ]


# ── Sweep detection ───────────────────────────────────────

def detect_sweep(bars: list, session_levels: list, tf: str) -> dict:
    """
    Detect a liquidity sweep on a specific timeframe.
    Checks the last 3 closed bars.
    Returns sweep dict or None.
    """
    if len(bars) < 3 or not session_levels:
        return None

    for i in range(len(bars) - 1, max(len(bars) - 4, 0), -1):
        bar = bars[i]
        for level in session_levels:
            # Short sweep: wick above high, close back below
            if bar["high"] >= level["high"] and bar["close"] < level["high"]:
                return {
                    "direction":   "short",
                    "level_type":  "session high",
                    "level_price": level["high"],
                    "level_date":  level["date"],
                    "sweep_high":  bar["high"],
                    "close_price": bar["close"],
                    "sweep_size":  round(bar["high"] - level["high"], 2),
                    "bar_idx":     i,
                    "trigger_tf":  tf,
                }
            # Long sweep: wick below low, close back above
            if bar["low"] <= level["low"] and bar["close"] > level["low"]:
                return {
                    "direction":   "long",
                    "level_type":  "session low",
                    "level_price": level["low"],
                    "level_date":  level["date"],
                    "sweep_low":   bar["low"],
                    "close_price": bar["close"],
                    "sweep_size":  round(level["low"] - bar["low"], 2),
                    "bar_idx":     i,
                    "trigger_tf":  tf,
                }
    return None


# ── Main MTF context builder ──────────────────────────────

def build_mtf_context(mtf_bars: dict, trigger_tf: str) -> dict:
    """
    Build full multi-timeframe context.

    mtf_bars  : {"1d": [...], "15m": [...], "5m": [...]}
    trigger_tf: which TF's bar close triggered this call ("15m" or "5m")

    Returns a rich context dict ready for Claude and Discord,
    or empty dict if no sweep or insufficient alignment.
    """
    bars_1d  = mtf_bars.get("1d",  [])
    bars_15m = mtf_bars.get("15m", [])
    bars_5m  = mtf_bars.get("5m",  [])

    if not bars_1d or not bars_5m:
        return {}

    # ── Trends per TF ─────────────────────────────────────
    trends = compute_all_trends(mtf_bars)

    # ── Session levels from 1D (daily H/L) ────────────────
    session_levels = compute_session_levels(bars_1d)

    # ── Sweep on trigger TF ───────────────────────────────
    trigger_bars   = mtf_bars.get(trigger_tf, [])
    sweep          = detect_sweep(trigger_bars, session_levels, trigger_tf)
    if not sweep:
        return {}

    direction      = sweep["direction"]

    # ── TF alignment ──────────────────────────────────────
    alignment      = count_tf_alignment(trends, direction)
    if alignment["aligned"] < MIN_TF_ALIGNMENT:
        return {"insufficient_alignment": True, "alignment": alignment, "sweep": sweep}

    # ── Market data (use 5m for VWAP/volume, 1d for POC) ─
    current_price  = trigger_bars[-1]["close"] if trigger_bars else 0.0
    vwap           = compute_vwap(bars_5m)
    session_pocs   = compute_session_pocs(bars_1d)
    poc_primary    = session_pocs[0]["poc"] if session_pocs else 0.0

    vol_stats      = compute_volume_stats(trigger_bars)

    # ── Intraday SMA Magnet Levels (15m & 5m) ─────────────
    intraday_15m   = compute_intraday_sma_levels(bars_15m, current_price, "15m", direction)
    intraday_5m    = compute_intraday_sma_levels(bars_5m, current_price, "5m", direction)
    intraday_sma_score = intraday_15m.get("magnet_score", 0) + intraday_5m.get("magnet_score", 0)
    intraday_breakout_score = intraday_15m.get("breakout_score", 0) + intraday_5m.get("breakout_score", 0)

    # ── Distance calculations ─────────────────────────────
    vwap_dist  = abs(current_price - vwap)        if vwap        else 999
    poc_dist   = abs(current_price - poc_primary)  if poc_primary else 999
    above_vwap = current_price > vwap              if vwap        else False
    near_poc   = poc_dist  <= POC_PROXIMITY_PTS
    near_vwap  = vwap_dist <= VWAP_PROXIMITY_PTS

    # ── Core conditions ───────────────────────────────────
    htf_trend      = trends.get("1d", {}).get("trend", "unknown")
    htf_aligned    = (direction == "short" and htf_trend == "bear") or \
                     (direction == "long"  and htf_trend == "bull")

    conditions = {
        "sweep_confirmed":   True,
        "reversal_candle":   True,
        "near_poc":          near_poc,
        "vwap_confluence":   (direction == "short" and not above_vwap) or
                             (direction == "long"  and above_vwap),
        "1h_trend_aligned":  htf_aligned,
        "tf_3plus_aligned":  alignment["aligned"] >= MIN_TF_ALIGNMENT,
        "rth_session":       is_rth(trigger_bars[-1]["timestamp"]),
    }
    score = sum(1 for v in conditions.values() if v)

    # ── Daily SMA Magnet Levels ───────────────────────────
    daily_sma = compute_daily_sma_levels(bars_1d, current_price, direction)
    daily_sma_score = daily_sma.get("magnet_score", 0)
    daily_breakout_score = daily_sma.get("breakout_score", 0)

    # ── SPX/SPY levels ────────────────────────────────────
    levels_ctx     = analyze_levels(current_price)
    nearest_levels = get_nearest_levels(current_price)

    spy_hit   = any(h.instrument == "SPY" and not h.is_pivot for h in levels_ctx.hits)
    spx_hit   = any(h.instrument == "SPX" and not h.is_pivot for h in levels_ctx.hits)
    pivot_hit = any(h.is_pivot for h in levels_ctx.hits)

    ext_conditions = {
        "near_spy_level": spy_hit,
        "near_spx_level": spx_hit,
        "near_pivot":     pivot_hit,
    }
    ext_score = levels_ctx.score_boost

    # ── Calculate TP/SL Estimates (based on confluence score and sweep size) ─
    sweep_size = sweep.get("sweep_size", 20)  # Points beyond level

    # Confluence score drives distance multiplier (0.5x to 2.0x)
    # Score = base + ext + daily_sma + daily_breakout + intraday_sma + intraday_breakout
    confluence_raw = (score + ext_score +
                     daily_sma_score + daily_breakout_score +
                     intraday_sma_score + intraday_breakout_score)
    score_multiplier = 0.5 + (confluence_raw / 10.0) * 1.5  # Maps 0→0.5, 10→2.0
    score_multiplier = min(2.0, max(0.5, score_multiplier))  # Clamp to [0.5, 2.0]

    # Scale SL distance based on sweep size and confluence
    sl_distance = max(15, sweep_size * 0.5 * score_multiplier)  # Min 15pts

    if direction == "long":
        sl_estimate = current_price - sl_distance
        tp_estimate = current_price + (sl_distance * 1.5)  # TP = 1.5x SL distance (2:1 R:R)
    else:  # short
        sl_estimate = current_price + sl_distance
        tp_estimate = current_price - (sl_distance * 1.5)

    # Calculate R:R ratio
    risk_distance = abs(sl_estimate - current_price)
    reward_distance = abs(tp_estimate - current_price)
    rr_ratio = reward_distance / risk_distance if risk_distance > 0 else 0

    return {
        # Core
        "current_price":    current_price,
        "direction":        direction,
        "trigger_tf":       trigger_tf,
        "timestamp":        trigger_bars[-1]["timestamp"].isoformat(),
        "is_rth":           is_rth(trigger_bars[-1]["timestamp"]),

        # MTF trends
        "trends":           trends,
        "alignment":        alignment,

        # Market data
        "vwap":             round(vwap, 2),
        "poc_primary":      round(poc_primary, 2),
        "session_pocs":     session_pocs,
        "above_vwap":       above_vwap,
        "near_poc":         near_poc,
        "near_vwap":        near_vwap,
        "vwap_dist":        round(vwap_dist, 2),
        "poc_dist":         round(poc_dist, 2),
        "vol_stats":        vol_stats,

        # Session levels
        "session_levels":   session_levels,
        "sweep":            sweep,

        # Scoring
        "conditions":       conditions,
        "ext_conditions":   ext_conditions,
        "confluence_score": confluence_raw,
        "base_score":       score,
        "ext_score":        ext_score,
        "daily_sma_score":  daily_sma_score,
        "daily_breakout_score": daily_breakout_score,
        "intraday_sma_score": intraday_sma_score,
        "intraday_breakout_score": intraday_breakout_score,
        "total_conditions": len(conditions) + len(ext_conditions),

        # SMA Levels (Support/Resistance Magnet + Breakouts)
        "daily_sma":        daily_sma,
        "intraday_15m":     intraday_15m,
        "intraday_5m":      intraday_5m,

        # SPX/SPY
        "levels_ctx":       levels_ctx,
        "nearest_levels":   nearest_levels,

        # TP/SL Estimates
        "tp_estimate":      round(tp_estimate, 2),
        "sl_estimate":      round(sl_estimate, 2),
        "rr_estimate":      round(rr_ratio, 2),

        # Meta
        "bars_available":   {tf: len(mtf_bars[tf]) for tf in mtf_bars},
        "session_count":    len(session_levels),
    }
