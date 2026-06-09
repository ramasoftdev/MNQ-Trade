"""
SPX / SPY Levels Analyzer
===========================
Parses daily_levels.py, checks MNQ price proximity to each level,
and scores the confluence boost. Pivot gets special treatment.

SPY proximity threshold : 1.0 point
SPX proximity threshold : 5.0 points
Pivot score boost       : +2 (vs +1 for regular levels)
"""

import importlib
import importlib.util
import os
import logging
from dataclasses import dataclass, field
from datetime import datetime
import pytz

log = logging.getLogger("levels_analyzer")

# ── Thresholds ────────────────────────────────────────────
SPY_PROXIMITY  = 1.0    # points — SPY is priced ~10x lower than SPX
SPX_PROXIMITY  = 5.0    # points
PIVOT_BOOST    = 2      # extra confluence points for pivot touch
LEVEL_BOOST    = 1      # confluence points for regular level touch

LEVELS_FILE = os.path.join(os.path.dirname(__file__), "daily_levels.py")


@dataclass
class LevelHit:
    instrument: str       # "SPY" or "SPX"
    price:      float     # the level price
    is_pivot:   bool      # True if this is the pivot level
    distance:   float     # how far MNQ price is from this level
    direction:  str       # "above" or "below" (price relative to level)
    boost:      int       # confluence score contribution


@dataclass
class LevelsContext:
    date:           str
    spy_pivot:      float
    spx_pivot:      float
    spy_levels:     list
    spx_levels:     list
    hits:           list = field(default_factory=list)
    score_boost:    int  = 0
    near_spy_pivot: bool = False
    near_spx_pivot: bool = False
    pivot_acting_as: str = ""   # "support", "resistance", or ""
    summary:        str  = ""


# ── Parser ────────────────────────────────────────────────

def _parse_levels(raw: str) -> tuple:
    """
    Parse a multiline string of prices.
    Returns (levels_list, pivot_price)
    levels_list = [{"price": float, "is_pivot": bool}]
    """
    levels = []
    pivot  = None

    for line in raw.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        is_pivot = "PIVOT" in line.upper()
        # Extract first float-like token from line
        tokens = line.replace(",", "").split()
        for token in tokens:
            try:
                price = float(token)
                levels.append({"price": price, "is_pivot": is_pivot})
                if is_pivot:
                    pivot = price
                break
            except ValueError:
                continue

    return sorted(levels, key=lambda x: x["price"], reverse=True), pivot


def load_levels() -> tuple:
    """
    Load and parse daily_levels.py.
    Returns (spy_levels, spx_levels, spy_pivot, spx_pivot, date)
    Reloads from disk every call so morning updates are picked up automatically.
    """
    try:
        spec = importlib.util.spec_from_file_location("daily_levels", LEVELS_FILE)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        spy_levels, spy_pivot = _parse_levels(getattr(mod, "SPY", ""))
        spx_levels, spx_pivot = _parse_levels(getattr(mod, "SPX", ""))
        date = getattr(mod, "DATE", "unknown")

        log.info(
            f"Loaded levels for {date}: "
            f"SPY {len(spy_levels)} levels (pivot={spy_pivot}), "
            f"SPX {len(spx_levels)} levels (pivot={spx_pivot})"
        )
        return spy_levels, spx_levels, spy_pivot, spx_pivot, date

    except Exception as e:
        log.error(f"Failed to load daily_levels.py: {e}")
        return [], [], None, None, "unknown"


def check_levels_date(loaded_date: str) -> bool:
    """
    Check if the loaded date matches today's system date.
    Returns True if match, False if outdated.
    Logs a warning if outdated.
    """
    try:
        # Get today's date in Eastern Time (system timezone)
        tz = pytz.timezone("America/Chicago")
        today = datetime.now(tz).strftime("%Y-%m-%d")

        if loaded_date != today:
            log.warning(
                f"⚠️  PIVOT UPDATE NEEDED! ⚠️"
                f"\n   Loaded date: {loaded_date}"
                f"\n   Today's date: {today}"
                f"\n   The SPY/SPX levels may be OUTDATED."
                f"\n   Please update daily_levels.py with today's levels before trading."
            )
            return False
        return True
    except Exception as e:
        log.warning(f"Could not verify levels date: {e}")
        return True  # Don't fail on this check


def parse_levels_from_file() -> dict:
    """
    Load daily levels and check if date is current.
    Returns a dict with 'spy', 'spx', and 'date' keys.
    Warns if levels are outdated.
    """
    spy_levels, spx_levels, spy_pivot, spx_pivot, date = load_levels()

    # Check if levels are current
    check_levels_date(date)

    return {
        "spy": {
            "pivot": spy_pivot,
            "levels": [l["price"] for l in spy_levels],
        },
        "spx": {
            "pivot": spx_pivot,
            "levels": [l["price"] for l in spx_levels],
        },
        "date": date,
    }


# ── MNQ <-> SPX/SPY price conversion ─────────────────────

def mnq_to_spx_approx(mnq_price: float) -> float:
    """
    Approximate SPX equivalent from MNQ price.
    MNQ tracks NQ which tracks Nasdaq-100.
    SPX is S&P 500 — different index but highly correlated intraday.
    This conversion is approximate — used only for proximity check.
    NQ / MNQ point value ≈ SPX * 4.7 (rough historical ratio, update if drift)
    """
    return mnq_price / 4.7


def mnq_to_spy_approx(mnq_price: float) -> float:
    """
    Approximate SPY equivalent from MNQ price.
    SPY ≈ SPX / 10 approximately.
    """
    return mnq_to_spx_approx(mnq_price) / 10.0


# ── Main analyzer ─────────────────────────────────────────

def analyze_levels(mnq_price: float) -> LevelsContext:
    """
    Check MNQ price against today's SPX/SPY levels.
    Returns a LevelsContext with all hits and score boost.
    """
    spy_levels, spx_levels, spy_pivot, spx_pivot, date = load_levels()

    ctx = LevelsContext(
        date      = date,
        spy_pivot = spy_pivot or 0.0,
        spx_pivot = spx_pivot or 0.0,
        spy_levels= spy_levels,
        spx_levels= spx_levels,
    )

    # Convert MNQ price to approximate SPX and SPY equivalents
    spx_equiv = mnq_to_spx_approx(mnq_price)
    spy_equiv = mnq_to_spy_approx(mnq_price)

    hits = []

    # ── Check SPY levels ──────────────────────────────────
    for level in spy_levels:
        dist = abs(spy_equiv - level["price"])
        if dist <= SPY_PROXIMITY:
            direction = "above" if spy_equiv > level["price"] else "below"
            boost = PIVOT_BOOST if level["is_pivot"] else LEVEL_BOOST
            hits.append(LevelHit(
                instrument = "SPY",
                price      = level["price"],
                is_pivot   = level["is_pivot"],
                distance   = round(dist, 2),
                direction  = direction,
                boost      = boost,
            ))
            if level["is_pivot"]:
                ctx.near_spy_pivot = True

    # ── Check SPX levels ──────────────────────────────────
    for level in spx_levels:
        dist = abs(spx_equiv - level["price"])
        if dist <= SPX_PROXIMITY:
            direction = "above" if spx_equiv > level["price"] else "below"
            boost = PIVOT_BOOST if level["is_pivot"] else LEVEL_BOOST
            hits.append(LevelHit(
                instrument = "SPX",
                price      = level["price"],
                is_pivot   = level["is_pivot"],
                distance   = round(dist, 2),
                direction  = direction,
                boost      = boost,
            ))
            if level["is_pivot"]:
                ctx.near_spx_pivot = True

    ctx.hits        = hits
    ctx.score_boost = sum(h.boost for h in hits)

    # ── Pivot behavior analysis ───────────────────────────
    # Determine if price is using pivot as support or resistance
    pivot_hits = [h for h in hits if h.is_pivot]
    if pivot_hits:
        hit = pivot_hits[0]
        if hit.direction == "above":
            ctx.pivot_acting_as = "support"
        else:
            ctx.pivot_acting_as = "resistance"

    # ── Summary string for Claude ─────────────────────────
    if not hits:
        ctx.summary = "Price not near any SPX/SPY key levels today."
    else:
        parts = []
        for h in hits:
            pivot_tag = " [PIVOT]" if h.is_pivot else ""
            parts.append(
                f"{h.instrument} {h.price}{pivot_tag} "
                f"({h.distance:.2f}pts away, price is {h.direction})"
            )
        ctx.summary = " | ".join(parts)
        if ctx.pivot_acting_as:
            ctx.summary += f" | Pivot acting as {ctx.pivot_acting_as.upper()}"

    log.info(
        f"Levels check: SPX_equiv={spx_equiv:.1f} SPY_equiv={spy_equiv:.2f} "
        f"hits={len(hits)} boost=+{ctx.score_boost}"
    )

    return ctx


# ── Nearest levels (for Claude context) ──────────────────

def get_nearest_levels(mnq_price: float, n: int = 3) -> dict:
    """
    Returns the N nearest SPX and SPY levels above and below
    current price — useful for TP target identification.
    """
    spy_levels, spx_levels, spy_pivot, spx_pivot, date = load_levels()
    spx_equiv = mnq_to_spx_approx(mnq_price)
    spy_equiv = mnq_to_spy_approx(mnq_price)

    def nearest(levels, equiv, count):
        above = sorted(
            [l for l in levels if l["price"] > equiv],
            key=lambda x: x["price"]
        )[:count]
        below = sorted(
            [l for l in levels if l["price"] <= equiv],
            key=lambda x: x["price"],
            reverse=True
        )[:count]
        return above, below

    spy_above, spy_below = nearest(spy_levels, spy_equiv, n)
    spx_above, spx_below = nearest(spx_levels, spx_equiv, n)

    return {
        "spy_above": spy_above,
        "spy_below": spy_below,
        "spx_above": spx_above,
        "spx_below": spx_below,
        "spy_pivot": spy_pivot,
        "spx_pivot": spx_pivot,
        "date":      date,
    }
