"""
SPY Level Analysis with Magnet Logic
=====================================
Pivot acts as a magnet — price gets pulled back to it
regardless of direction (above or below).

Distance decay scoring:
  - Very close (< 0.30 pts): +2.5 points (strongest magnet)
  - Close (0.30-1.00 pts): +1.5 points
  - Medium (1.00-2.00 pts): +1.0 points
  - Far (> 2.00 pts): +0.0 points (magnet too weak)

Other levels: only count if within 0.30 pts, valued at +0.5 each (support/resistance)
"""

import logging

log = logging.getLogger("spy_levels_analyzer")


def analyze_spy_levels(spy_price, levels_config):
    """
    Analyze SPY price relative to pivot and other levels.

    Args:
        spy_price: Current SPY price (float)
        levels_config: dict with 'pivot' and 'levels' keys
                      {
                        'pivot': 756.40,
                        'levels': [767.50, 764.40, 762.30, ...]
                      }

    Returns:
        {
            'pivot_price': 756.40,
            'pivot_distance': 0.15,
            'pivot_direction': 'bullish' or 'bearish',
            'pivot_score': 2.0,
            'other_levels_hit': [{'level': 754.60, 'distance': 1.65}],
            'other_levels_score': 1.0,
            'total_spy_score': 3.0,
            'analysis': "SPY 756.25 below PIVOT 756.40 (bearish, very strong magnet)"
        }
    """

    if not levels_config or 'pivot' not in levels_config:
        return {
            'pivot_price': None,
            'pivot_distance': None,
            'pivot_direction': None,
            'pivot_score': 0.0,
            'other_levels_hit': [],
            'other_levels_score': 0.0,
            'total_spy_score': 0.0,
            'analysis': "No SPY levels configured"
        }

    pivot = levels_config.get('pivot')
    other_levels = levels_config.get('levels', [])

    # ── PIVOT MAGNET ANALYSIS ──────────────────────────────
    pivot_distance = abs(spy_price - pivot)
    above_pivot = spy_price > pivot

    # Magnet strength scoring (distance-based)
    if pivot_distance < 0.30:
        pivot_score = 2.5
        magnet_strength = "very strong magnet"
    elif pivot_distance < 1.00:
        pivot_score = 1.5
        magnet_strength = "strong magnet"
    elif pivot_distance < 2.00:
        pivot_score = 1.0
        magnet_strength = "weak magnet"
    else:
        pivot_score = 0.0
        magnet_strength = "no magnet effect"

    direction = "bullish" if above_pivot else "bearish"

    # ── OTHER LEVELS (SIMPLE HITS) ─────────────────────────
    other_levels_hit = []
    for level in other_levels:
        if level == pivot:
            continue  # Skip pivot, already counted
        distance = abs(spy_price - level)
        if distance < 0.30:  # Only count if very close
            other_levels_hit.append({
                'level': level,
                'distance': round(distance, 2)
            })

    other_levels_score = len(other_levels_hit) * 0.5

    # ── ANALYSIS STRING ────────────────────────────────────
    analysis = (
        f"SPY {spy_price:.2f} {'above' if above_pivot else 'below'} "
        f"PIVOT {pivot:.2f} ({direction}, {magnet_strength})"
    )

    if other_levels_hit:
        hit_str = ", ".join([f"{h['level']:.2f}" for h in other_levels_hit])
        analysis += f" | Also near: {hit_str}"

    return {
        'pivot_price': pivot,
        'pivot_distance': round(pivot_distance, 2),
        'pivot_direction': direction,
        'pivot_score': pivot_score,
        'other_levels_hit': other_levels_hit,
        'other_levels_score': other_levels_score,
        'total_spy_score': pivot_score + other_levels_score,
        'analysis': analysis
    }


def get_pivot_direction_bonus(sweep_direction, spy_direction):
    """
    Extra bonus if sweep direction aligns with SPY position vs pivot.

    Args:
        sweep_direction: 'long' or 'short'
        spy_direction: 'bullish' or 'bearish'

    Returns:
        float: bonus points (0.5 or 0.0)
    """

    if sweep_direction == 'long' and spy_direction == 'bullish':
        return 0.5  # LONG sweep + SPY above pivot = aligned
    elif sweep_direction == 'short' and spy_direction == 'bearish':
        return 0.5  # SHORT sweep + SPY below pivot = aligned
    else:
        return 0.0  # Misaligned (still tradeable, but less confluence)


def format_spy_score_detail(spy_analysis, direction_bonus):
    """
    Format detailed SPY scoring for logging.

    Returns:
        str: formatted detail line
    """

    pivot_score = spy_analysis['pivot_score']
    other_score = spy_analysis['other_levels_score']
    direction_bonus = direction_bonus
    total = pivot_score + other_score + direction_bonus

    detail = (
        f"Pivot {pivot_score:.1f} + "
        f"Others {other_score:.1f} + "
        f"Direction {direction_bonus:.1f} = {total:.1f} pts"
    )

    return detail
