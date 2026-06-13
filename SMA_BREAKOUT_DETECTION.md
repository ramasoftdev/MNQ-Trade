# SMA Breakout Detection System

## Overview

Added **strength-based SMA breakout detection** to identify decisive price breaks through moving average levels.

---

## What Is a Breakout?

A **breakout** occurs when price breaks through a moving average level with momentum:

```
Before: Price is below SMA(50)
After:  Price is above SMA(50) by X points
→ BULLISH BREAKOUT (for LONG trades)
```

---

## Breakout Strength Scoring

Based on **how far** price has broken through the SMA:

| Distance | Score | Signal Strength |
|----------|-------|-----------------|
| 1-2 pts | +0.5 | Just crossed (weak) |
| 5-10 pts | +1.0 | Solid break (good) |
| 10+ pts | +1.5 | Strong break (very good) |
| < 1 pt | +0.0 | Not a confirmed breakout |

---

## Applied To All Timeframes

### Daily SMAs (5, 20, 50, 100, 200)
```
LONG Setup:
├─ Price breaks ABOVE SMA(50) by 8 pts → +1.0 (solid breakout)
├─ Price breaks ABOVE SMA(100) by 15 pts → +1.5 (strong breakout)
└─ Daily Breakout Score: 2.5 points

SHORT Setup:
├─ Price breaks BELOW SMA(50) by 8 pts → +1.0
├─ Price breaks BELOW SMA(100) by 15 pts → +1.5
└─ Daily Breakout Score: 2.5 points
```

### 15m SMAs (5, 20, 50)
```
Same logic - score for each SMA the price has broken through
```

### 5m SMAs (5, 20, 50)
```
Same logic - score for each SMA the price has broken through
```

---

## How It Works

### Step 1: Detect Breakouts
```python
For each SMA level:
  ├─ Calculate distance = current_price - sma_price
  ├─ Check if direction matches (LONG = price > SMA, SHORT = price < SMA)
  └─ If valid breakout → score it by strength
```

### Step 2: Score Each Breakout
```python
if abs(distance) >= 10:
    score = 1.5  # Strong break
elif abs(distance) >= 5:
    score = 1.0  # Solid break
elif abs(distance) >= 1:
    score = 0.5  # Just crossed
else:
    score = 0.0  # Not confirmed
```

### Step 3: Combine All Breakouts
```python
Daily Breakout Score = sum of all daily SMA breakouts
Intraday Breakout Score = (15m SMAs) + (5m SMAs)
Total Breakout Score = Daily + Intraday
```

---

## Confluence Score Calculation

```
Total Confluence = Base + Ext + Magnet + Breakout

Where:
├─ Base = sweep + conditions (up to 5 pts)
├─ Ext = SPY/SPX levels (up to 2 pts)
├─ Magnet = distance to SMAs (up to 6 pts total: 2+2+2)
└─ Breakout = strength of breaks (up to 15 pts total: 7.5+3.75+3.75)

MAXIMUM POSSIBLE: 5 + 2 + 6 + 15 = 28 points
EXCELLENT SIGNAL: 15+ points
GOOD SIGNAL: 10-14 points
MODERATE: 7-9 points
WEAK: < 7 points
```

---

## Example: Strong Breakout Signal

```
Current Price: 29,766.75
Direction: LONG

═══ DAILY BREAKOUTS ═══
SMA(5):   29,765.00  → 1.75 pts above → No breakout (< 1 pt threshold)
SMA(20):  29,750.00  → 16.75 pts above → +1.5 (strong)
SMA(50):  29,760.00  → 6.75 pts above → +1.0 (solid)
SMA(100): 29,755.00  → 11.75 pts above → +1.5 (strong)
SMA(200): 29,740.00  → 26.75 pts above → +1.5 (strong)
Daily Breakout Score: 5.5

═══ 15m BREAKOUTS ═══
SMA(5):   29,764.00  → 2.75 pts above → +0.5
SMA(20):  29,760.00  → 6.75 pts above → +1.0
SMA(50):  29,758.00  → 8.75 pts above → +1.0
15m Breakout Score: 2.5

═══ 5m BREAKOUTS ═══
SMA(5):   29,765.50  → 1.25 pts above → No breakout
SMA(20):  29,762.00  → 4.75 pts above → +0.5
SMA(50):  29,755.00  → 11.75 pts above → +1.5
5m Breakout Score: 2.0

═══ TOTAL CONFLUENCE ═══
Base:                    5
External:                1
Daily Magnet:           3.0
Daily Breakout:         5.5
15m Magnet:            1.5
15m Breakout:          2.5
5m Magnet:             3.0
5m Breakout:           2.0
────────────────────────
TOTAL CONFLUENCE:      23.5 ⭐⭐⭐

Signal Quality: EXCELLENT
→ Price has broken through MULTIPLE moving averages decisively
→ Confirms strong institutional momentum
→ High confidence LONG entry
```

---

## Alert Data Structure

When an alert is generated with breakouts:

```python
{
    "confluence_score": 23.5,
    "base_score": 5,
    "ext_score": 1,
    
    # Magnet Scores
    "daily_sma_score": 3.0,
    "intraday_sma_score": 4.5,
    
    # NEW: Breakout Scores
    "daily_breakout_score": 5.5,
    "intraday_breakout_score": 4.5,
    
    # Daily SMA Data (with breakouts)
    "daily_sma": {
        "magnet_score": 3.0,
        "breakout_score": 5.5,
        "breakouts": [
            {
                "period": 20,
                "sma_price": 29750.00,
                "distance": 16.75,
                "score": 1.5,
                "type": "bullish"  # or "bearish" for SHORT
            },
            {
                "period": 50,
                "sma_price": 29760.00,
                "distance": 6.75,
                "score": 1.0,
                "type": "bullish"
            },
            # ... more breakouts
        ],
        "hits": [...],  # Magnet levels
        "smas": {...}
    },
    
    # Intraday SMA Data (with breakouts)
    "intraday_15m": {
        "magnet_score": 1.5,
        "breakout_score": 2.5,
        "breakouts": [...],
        "crosses": {"cross_type": "golden", ...},
        ...
    },
    "intraday_5m": {
        "magnet_score": 3.0,
        "breakout_score": 2.0,
        "breakouts": [...],
        "crosses": {"cross_type": "golden", ...},
        ...
    }
}
```

---

## Key Signals in Combination

### Signal Type 1: Magnet + Breakout (VERY STRONG)
```
Price near SMA (magnet) AND broke through it decisively
→ Institutional level confirmed with momentum
→ Highest confidence setup
```

### Signal Type 2: Breakout Only (STRONG)
```
Price broke through multiple SMAs by good distance
→ Strong momentum even if not at exact magnet
→ Good confidence
```

### Signal Type 3: Magnet Only (MODERATE)
```
Price near SMA but hasn't broken decisively yet
→ Key level identified but needs momentum
→ Wait for breakout confirmation
```

### Signal Type 4: Multiple Timeframe Breakouts (EXCELLENT)
```
Daily + 15m + 5m all showing breakouts
→ All timeframes aligned with momentum
→ Highest quality setups
```

---

## Breakout vs. Golden Cross

| Type | What It Detects | Use Case |
|------|-----------------|----------|
| **Breakout** | Price breaks through a single SMA with distance-based strength | Institutional momentum moves |
| **Golden Cross** | Fast SMA crosses above slow SMA (5 > 20 > 50) | Trend shift / momentum change |
| **Magnet** | Price near an SMA (acts as S/R) | Key institutional levels |

**All three work together:**
- Breakout scores the decisiveness
- Golden Cross confirms the direction
- Magnet shows the level's importance

---

## Testing Breakout Detection

```bash
python << 'EOF'
from src.analysis.context_analyzer import score_breakout_strength, detect_sma_breakouts

# Test scoring function
print("Breakout Scoring Tests:")
print(f"1 pt distance: {score_breakout_strength(1.0)} (expect 0.5)")
print(f"6 pt distance: {score_breakout_strength(6.0)} (expect 1.0)")
print(f"12 pt distance: {score_breakout_strength(12.0)} (expect 1.5)")
print()

# Test breakout detection
bars = [...]  # Your bar data
smas = {"sma_5": 100, "sma_20": 99, "sma_50": 98}
current_price = 108  # 8 pts above SMA(20)

result = detect_sma_breakouts(bars, smas, "long")
print(f"Breakout Score: {result['breakout_score']}")
print(f"Breakouts: {result['breakouts']}")
EOF
```

---

## Implementation Details

### Functions Added

1. **`score_breakout_strength(distance: float) -> float`**
   - Converts distance to a score (0.0-1.5)
   - Returns 0 for distances < 1 pt

2. **`detect_sma_breakouts(bars, smas, direction) -> dict`**
   - Detects all SMA breakouts for the given direction
   - Scores each by strength
   - Returns total breakout_score and list of breakouts

3. **Updated: `compute_intraday_sma_levels()`**
   - Now includes breakout detection
   - Returns both magnet_score and breakout_score

4. **Updated: `compute_daily_sma_levels()`**
   - Now includes breakout detection
   - Returns both magnet_score and breakout_score

5. **Updated: `build_mtf_context()`**
   - Computes all breakout scores
   - Adds to confluence calculation
   - Includes breakout data in alert info

---

## Live Example

When you run the agent next:

```bash
rm -f src/trading/trades.db
python src/core/run.py
```

Next alert will include:

```
Alert Context:
├─ Daily Breakouts: 5.5
├─ 15m Breakouts: 2.5
├─ 5m Breakouts: 2.0
├─ Total Breakout Score: 10.0
└─ Confluence Score: 23.5 (includes all components)

Breakout Details:
├─ SMA(20) broken 16.75 pts (strong)
├─ SMA(50) broken 6.75 pts (solid)
├─ 15m Golden Cross detected
└─ Multiple timeframe alignment ✓
```

---

## Summary

The system now detects **three types of SMA signals:**

1. **Magnet Levels** - Distance-based scores for proximity
2. **Golden/Death Crosses** - Momentum direction shifts
3. **Breakouts** - Strength-based scores for momentum

**Combined**, they create a **comprehensive confluence system** that:
- ✅ Identifies institutional levels (magnet)
- ✅ Detects momentum shifts (golden cross)
- ✅ Measures breakout strength (breakout)
- ✅ Filters low-quality setups (high confluence threshold)
- ✅ Estimates better SL/TP (higher score = wider TP/tighter SL)

🚀 **Ready to test!**
