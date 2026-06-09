# SPY Pivot Magnet Logic — Implementation Guide

## Overview

The SPY levels system now treats the **PIVOT as a magnet** that attracts price regardless of which side it's on (above or below). Distance from the pivot determines the strength of the score.

---

## How It Works

### **Pivot Magnet Scoring (Distance-Based)**

```
Distance from PIVOT:
  < 0.30 pts    → +2.5 points (very strong magnet)
  < 1.00 pts    → +1.5 points (strong magnet)
  < 2.00 pts    → +1.0 points (weak magnet)
  >= 2.00 pts   → +0.0 points (no magnet effect)
```

### **Direction Bias**

```
SPY above PIVOT  → bullish bias
SPY below PIVOT  → bearish bias

Direction Bonus (+0.5):
  ├─ LONG sweep + SPY above PIVOT = aligned ✓
  ├─ SHORT sweep + SPY below PIVOT = aligned ✓
  └─ Opposite = not aligned (but still counts magnet score)
```

### **Other Levels (Simple Support/Resistance)**

```
Only count if price is within 0.30 pts
Each level hit = +0.5 points (used as support/resistance areas)

Examples:
  ├─ 753.20 level, SPY at 753.18 → hit, +0.5
  ├─ 753.20 level, SPY at 753.40 → no hit, +0.0
  └─ Multiple hits stack (+0.5 each)
```

---

## Files Changed

### **1. New: `spy_levels_analyzer.py`**

Core logic for magnet scoring:
- `analyze_spy_levels(spy_price, levels_config)` → returns analysis dict with magnet score
- `get_pivot_direction_bonus(sweep_direction, spy_direction)` → +0.5 or +0.0
- `format_spy_score_detail()` → readable logging

### **2. Updated: `config.py`**

Added magnet thresholds:
```python
SPY_PIVOT_MAGNET_THRESHOLDS = {
    'very_close': 0.30,
    'close': 1.00,
    'medium': 2.00,
}
SPY_OTHER_LEVELS_THRESHOLD = 0.30
SPY_PIVOT_DIRECTION_BONUS = 0.5
```

### **3. Updated: `daily_levels.py`**

Enhanced documentation explaining pivot magnet behavior:
- Mark ONE level with `PIVOT` keyword
- All other levels treated as static support/resistance
- Scoring rules documented at top

### **4. Updated: `agent.py`**

In `on_bar_close()` callback:
- Import `analyze_spy_levels()` and `get_pivot_direction_bonus()`
- Parse daily levels
- Analyze SPY magnet position
- Calculate direction bonus
- Add SPY score to confluence total
- Log detailed SPY analysis

---

## Confluence Score Breakdown

### **Before (old system)**
```
Core (8 points):
  ├─ Sweep, price confirm, VWAP, volume, trends, alignment, VWAP prox, RTH
  
SPY (2 points):
  ├─ Any level hit: +1
  ├─ PIVOT hit: +1
────────────
Total: 0-10 points
```

### **After (magnet system — updated)**
```
Core (8 points):
  ├─ Sweep, price confirm, VWAP, volume, trends, alignment, VWAP prox, RTH

SPY Magnet (up to 3.5+ points):
  ├─ Pivot distance scoring (0-2.5 points)
  │   └─ Very close (< 0.30 pts): +2.5
  │   └─ Close (< 1.00 pts): +1.5
  │   └─ Medium (< 2.00 pts): +1.0
  │   └─ Far (>= 2.00 pts): +0.0
  │
  ├─ Direction bonus: +0.5 if aligned
  │   └─ LONG + above pivot = bullish match
  │   └─ SHORT + below pivot = bearish match
  │
  └─ Other levels: +0.5 each (if within 0.30 pts, support/resistance)
────────────
Total: 0-12.5+ points
```

---

## Example Scenarios

### **Scenario 1: SHORT Sweep, SPY 756.25 (PIVOT 756.40)**

```
Distance: |756.25 - 756.40| = 0.15 pts
Direction: Below pivot = bearish ✓
Magnet strength: Very strong (< 0.30)

Scoring:
  ├─ Pivot magnet: +2.5 (very close)
  ├─ Direction bonus: +0.5 (SHORT + below)
  ├─ Other levels: +0.0
  └─ SPY total: +3.0
```

**Interpretation:** Very strong magnet pulling price down. SHORT sweep perfectly aligned.

---

### **Scenario 2: LONG Sweep, SPY 755.80 (PIVOT 756.40)**

```
Distance: |755.80 - 756.40| = 0.60 pts
Direction: Below pivot = bearish ✗
Magnet strength: Strong (< 1.00)

Scoring:
  ├─ Pivot magnet: +1.5 (close)
  ├─ Direction bonus: +0.0 (LONG + below = mismatch)
  ├─ Other levels: +0.0
  └─ SPY total: +1.5
```

**Interpretation:** Magnet pulling down (bearish), but LONG sweep trying to go up (misaligned). Still scores but lower.

---

### **Scenario 3: SHORT Sweep, SPY 752.00 (PIVOT 756.40)**

```
Distance: |752.00 - 756.40| = 4.40 pts
Direction: Below pivot = bearish ✓
Magnet strength: None (>= 2.00)

Scoring:
  ├─ Pivot magnet: +0.0 (too far)
  ├─ Direction bonus: +0.0
  ├─ Other levels: +0.0 or +0.5 if near 752.xx level (support/resistance)
  └─ SPY total: +0.0 to +0.5
```

**Interpretation:** Magnet effect worn off. Price too far from pivot. No magnet bonus. Other levels act as simple support/resistance.

---

### **Scenario 4: LONG Sweep, SPY 757.10 (PIVOT 756.40, Other level 757.20)**

```
Distance from pivot: |757.10 - 756.40| = 0.70 pts
Direction: Above pivot = bullish ✓
Magnet strength: Strong (< 1.00)
Other levels: 757.20 is 0.10 away → HIT (support/resistance area)

Scoring:
  ├─ Pivot magnet: +1.5 (close, strong)
  ├─ Direction bonus: +0.5 (LONG + above)
  ├─ Other levels: +0.5 (757.20 hit)
  └─ SPY total: +2.5
```

**Interpretation:** Strong magnet at pivot + direction aligned + additional level acting as resistance. Excellent SPY confluence.

---

## Daily Update Workflow

Each morning:

1. Open `daily_levels.py`
2. Update SPY levels (paste from your trader analysis)
3. **Mark ONE level with PIVOT** keyword:
   ```
   756.40 PIVOT
   ```
4. Save — agent automatically reloads on next alert

Example:
```python
SPY = """
767.50
764.30
762.00
756.70 PIVOT
753.90
752.20
749.80
"""
```

---

## Logging Output

When a sweep fires, you'll see:

```
19:35:42  INFO      agent  Bar closed on 5m (2713 bars in buffer)
19:35:42  INFO      agent  SPY magnet: SPY 756.25 below PIVOT 756.40 (bearish, very strong magnet)
19:35:42  INFO      agent  SPY score: Pivot 2.0 + Others 0.0 + Direction 0.5 = 2.5 pts
19:35:42  INFO      agent  SWEEP on 5m: SHORT @ 30440.50 | alignment 4/4 | score 10.5 (core + SPY magnet)
19:35:43  INFO      agent  Claude: 74% — TAKE (High confidence)
19:35:44  INFO      agent  Pipeline complete — Discord alert sent.
```

---

## Key Differences from Old System

| Aspect | Old | New |
|---|---|---|
| Pivot scoring | Fixed +1 per hit | Distance-based magnet (0-2.5) |
| Other levels | Any proximity counted | Only very close (< 0.30), +0.5 each (support/resistance) |
| Direction bias | Static support/resistance | Bullish/bearish vs pivot |
| Direction bonus | None | +0.5 if sweep aligned |
| Max SPY score | 2 points | 3.5+ points possible |

---

## Tuning

Want to adjust magnet thresholds? Edit `config.py`:

```python
SPY_PIVOT_MAGNET_THRESHOLDS = {
    'very_close': 0.30,   # ← increase to 0.50 for looser magnet
    'close': 1.00,        # ← increase to 1.50 for wider range
    'medium': 2.00,       # ← increase to 3.00 for even weaker effect
}
```

Or adjust direction bonus:
```python
SPY_PIVOT_DIRECTION_BONUS = 0.5  # ← change to 0.2 or 1.0
```

---

## Summary

The pivot magnet system rewards:
- ✅ Proximity to the key pivot level (distance-based)
- ✅ Direction alignment (SPY side matching sweep direction)
- ✅ Multiple confluence zones (other levels as static)

Result: More nuanced SPY confluence scoring that reflects how price is attracted to the pivot regardless of direction.
