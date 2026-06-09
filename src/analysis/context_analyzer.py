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
    NUM_SESSIONS, POC_SESSIONS, EMA_PERIODS, MIN_TF_ALIGNMENT,
    TIMEFRAMES,
)
from src.levels.levels_analyzer import analyze_levels, get_nearest_levels

TZ = pytz.timezone(TIMEZONE)
TF_LABEL = {"1h": "1-Hour", "30m": "30-Min", "15m": "15-Min", "5m": "5-Min"}


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

def compute_ema(values: list, period: int) -> float:
    if not values:
        return 0.0
    if len(values) < period:
        period = len(values)
    k   = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return ema


def compute_tf_trend(bars: list, tf: str) -> dict:
    """
    Compute EMA-based trend for a single timeframe.
    Returns {"trend": "bull"|"bear"|"unknown", "ema": float, "close": float}
    """
    period = EMA_PERIODS.get(tf, 50)
    closes = [b["close"] for b in bars if is_globex(b["timestamp"])]
    if len(closes) < 10:
        return {"trend": "unknown", "ema": 0.0, "close": 0.0}
    ema   = compute_ema(closes, min(period, len(closes)))
    close = closes[-1]
    return {
        "trend": "bull" if close > ema else "bear",
        "ema":   round(ema, 2),
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

    mtf_bars  : {"1h": [...], "30m": [...], "15m": [...], "5m": [...]}
    trigger_tf: which TF's bar close triggered this call ("15m" or "5m")

    Returns a rich context dict ready for Claude and Discord,
    or empty dict if no sweep or insufficient alignment.
    """
    bars_1h  = mtf_bars.get("1h",  [])
    bars_30m = mtf_bars.get("30m", [])
    bars_15m = mtf_bars.get("15m", [])
    bars_5m  = mtf_bars.get("5m",  [])

    if not bars_1h or not bars_5m:
        return {}

    # ── Trends per TF ─────────────────────────────────────
    trends = compute_all_trends(mtf_bars)

    # ── Session levels from 1H (most meaningful H/L) ──────
    session_levels = compute_session_levels(bars_1h)

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

    # ── Market data (use 5m for VWAP/volume, 30m for POC) ─
    current_price  = trigger_bars[-1]["close"] if trigger_bars else 0.0
    vwap           = compute_vwap(bars_5m)
    session_pocs   = compute_session_pocs(bars_30m)
    poc_primary    = session_pocs[0]["poc"] if session_pocs else 0.0

    vol_stats      = compute_volume_stats(trigger_bars)

    # ── Distance calculations ─────────────────────────────
    vwap_dist  = abs(current_price - vwap)        if vwap        else 999
    poc_dist   = abs(current_price - poc_primary)  if poc_primary else 999
    above_vwap = current_price > vwap              if vwap        else False
    near_poc   = poc_dist  <= POC_PROXIMITY_PTS
    near_vwap  = vwap_dist <= VWAP_PROXIMITY_PTS

    # ── Core conditions ───────────────────────────────────
    htf_trend      = trends["1h"]["trend"]
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
    # Lower scores (< 5) use 0.5x, higher scores (10+) use 2.0x
    confluence_raw = score + ext_score
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
        "confluence_score": score + ext_score,
        "base_score":       score,
        "ext_score":        ext_score,
        "total_conditions": len(conditions) + len(ext_conditions),

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
