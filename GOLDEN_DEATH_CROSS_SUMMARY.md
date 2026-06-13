# Golden Cross / Death Cross Implementation

## Overview

Added **Golden Cross and Death Cross detection** for 15m and 5m timeframes, combined with **SMA magnet level scoring** for support/resistance zones.

---

## What Are They?

### **Golden Cross** (Bullish Signal)
```
Condition: SMA(5) > SMA(20) > SMA(50)
Meaning: Fast-moving average crosses above slower ones
Signal: Strong uptrend, momentum shift to bullish
Scoring: Strongly reinforces LONG direction
```

### **Death Cross** (Bearish Signal)
```
Condition: SMA(5) < SMA(20) < SMA(50)
Meaning: Fast-moving average crosses below slower ones
Signal: Strong downtrend, momentum shift to bearish
Scoring: Strongly reinforces SHORT direction
```

---

## Implementation Details

### 15m Timeframe
```
SMAs: [5, 20, 50]

Golden Cross:
├─ SMA(5) > SMA(20) ✓
├─ SMA(20) > SMA(50) ✓
└─ Trend = BULL (strong confirmation)

Death Cross:
├─ SMA(5) < SMA(20) ✓
├─ SMA(20) < SMA(50) ✓
└─ Trend = BEAR (strong confirmation)

SMA Magnet Levels (Support/Resistance):
├─ Price near SMA(5)  → +2.0 (very close)
├─ Price near SMA(20) → +1.0 (close)
└─ Price near SMA(50) → +0.5 (medium)
```

### 5m Timeframe
```
SMAs: [5, 20, 50]

Same logic as 15m - Golden/Death cross detection +
SMA magnet level scoring
```

### Daily Timeframe
```
SMAs: [5, 20, 50, 100, 200]
(No cross detection, just trend + magnet levels)
```

---

## Confluence Scoring Formula

```
Total Confluence Score = 
    Base Score          (sweep + conditions)
  + External Score      (SPY/SPX pivots)
  + Daily SMA Score     (distance to daily SMAs)
  + Intraday SMA Score  (distance to 15m/5m SMAs + crosses)
```

### Example Alert With All Signals

```
Current Price: 29,766.75

═══ Daily Level ═══
SMA(5):   29,765.00  → 1.75 pts away → +2.0
SMA(50):  29,760.00  → 6.75 pts away → +1.0
Daily SMA Score: 3.0

═══ 15m Level ═══
SMA(5):   29,764.00  → 2.75 pts away → +1.0
SMA(20):  29,760.00  → 6.75 pts away → +0.5
Golden Cross Detected: SMA(5) > SMA(20) > SMA(50) ✓
Intraday 15m Score: 1.5

═══ 5m Level ═══
SMA(5):   29,765.50  → 1.25 pts away → +2.0
SMA(20):  29,762.00  → 4.75 pts away → +1.0
Golden Cross Detected: SMA(5) > SMA(20) > SMA(50) ✓
Intraday 5m Score: 3.0

═══ Total ═══
Base Score (conditions):     5 points
External Score (SPY):        1 point
Daily SMA Score:             3.0 points
Intraday SMA Score (15m+5m): 4.5 points
───────────────────────────
TOTAL CONFLUENCE:           13.5 points ⭐
```

---

## Functions Added/Updated

### New Functions

#### `detect_sma_crosses(closes: list, periods: list) -> dict`
Detects golden cross and death cross signals.

**Returns:**
```python
{
    "golden_cross": True/False,
    "death_cross": True/False,
    "cross_type": "golden" | "death" | "none",
    "smas": {"sma_5": X, "sma_20": Y, "sma_50": Z}
}
```

#### `compute_intraday_sma_levels(bars: list, current_price: float, tf: str) -> dict`
Compute 15m/5m SMA levels and score them as magnet levels. Includes cross detection.

**Returns:**
```python
{
    "smas": {"sma_5": ..., "sma_20": ..., "sma_50": ...},
    "magnet_score": 0.0-2.0,  # Distance-based magnet effect
    "nearest_sma": {"period": 5, "price": X, "distance": Y},
    "hits": [
        {"type": "15m_sma", "period": 5, "price": X, "distance": Y},
        ...
    ],
    "crosses": {
        "golden_cross": True,
        "death_cross": False,
        "cross_type": "golden"
    }
}
```

### Updated Functions

#### `detect_sma_crosses()` → `compute_tf_trend()`
Now includes:
- Cross detection (golden/death)
- Trend derived from crosses
- All SMA values
- Cross type indication

**Returns:**
```python
{
    "trend": "bull" | "bear",
    "cross_type": "golden" | "death" | "none",
    "sma_fast": 29764.50,
    "smas": {...},
    "close": 29766.75
}
```

#### `build_mtf_context()`
Now:
- Computes 15m SMA magnet levels + crosses
- Computes 5m SMA magnet levels + crosses
- Adds intraday SMA score to confluence
- Returns both intraday datasets

---

## Alert Data Structure

When an alert is generated, it now includes:

```python
{
    # Confluence Score Breakdown
    "confluence_score": 13.5,
    "base_score": 5,
    "ext_score": 1,
    "daily_sma_score": 3.0,
    "intraday_sma_score": 4.5,  # NEW
    
    # Trends with Cross Information
    "trends": {
        "1d": {
            "trend": "bull",
            "sma_fast": 29765.00,
            "smas": {"sma_5": 29765, "sma_20": 29750, ...},
            "close": 29766.75
        },
        "15m": {
            "trend": "bull",
            "cross_type": "golden",  # NEW
            "smas": {...},
            ...
        },
        "5m": {
            "trend": "bull",
            "cross_type": "golden",  # NEW
            "smas": {...},
            ...
        }
    },
    
    # SMA Magnet Data
    "daily_sma": {
        "magnet_score": 3.0,
        "hits": [...],
        "nearest_sma": {...}
    },
    "intraday_15m": {  # NEW
        "magnet_score": 1.5,
        "crosses": {"cross_type": "golden", ...},
        "hits": [...],
        ...
    },
    "intraday_5m": {  # NEW
        "magnet_score": 3.0,
        "crosses": {"cross_type": "golden", ...},
        "hits": [...],
        ...
    }
}
```

---

## Magnet Scoring Rules

**Applied to 15m, 5m, and Daily SMA levels:**

| Distance | Score | Meaning |
|----------|-------|---------|
| < 3 pts | +2.0 | Very close magnet (strong level) |
| 3-7 pts | +1.0 | Close magnet |
| 7-15 pts | +0.5 | Medium magnet |
| > 15 pts | +0.0 | Too far to count |

**Formula for combined score:**
```
Total = Sum of all SMA hits that are within 15 pts
```

---

## Example Scenario

### Setup
```
Time: 10:30 AM CT
Direction: LONG (sweep detected)
Current Price: 29,766.75

Daily:
├─ Trend: BULL (price > SMA(5))
├─ SMA(5): 29,765.00
├─ SMA(50): 29,760.00
└─ No crosses yet (daily is slower)

15m:
├─ Trend: BULL
├─ Cross: GOLDEN (SMA(5)>20>50)
├─ SMA(5): 29,764.00
└─ SMA(20): 29,760.00

5m:
├─ Trend: BULL
├─ Cross: GOLDEN (SMA(5)>20>50)
├─ SMA(5): 29,765.50
└─ SMA(20): 29,762.00
```

### Scoring Breakdown
```
Base Conditions: 5 pts
  ├─ Sweep confirmed: ✓
  ├─ Reversal candle: ✓
  ├─ VWAP confluence: ✓
  ├─ 1D trend aligned: ✓
  └─ TF alignment (3+): ✓

External (SPY): 1 pt
  └─ Near pivot level: ✓

Daily SMA Magnet: 3.0 pts
  ├─ Near SMA(5): 1.75 pts away → +2.0
  └─ Near SMA(50): 6.75 pts away → +1.0

Intraday 15m SMA: 1.5 pts
  ├─ Near SMA(5): 2.75 pts away → +1.0
  ├─ Near SMA(20): 6.75 pts away → +0.5
  └─ Golden Cross: BULL confirmation ✓

Intraday 5m SMA: 3.0 pts
  ├─ Near SMA(5): 1.25 pts away → +2.0
  ├─ Near SMA(20): 4.75 pts away → +1.0
  └─ Golden Cross: BULL confirmation ✓

TOTAL: 5 + 1 + 3.0 + 1.5 + 3.0 = 13.5 points ⭐

Confluence Level: VERY HIGH (13.5+ is excellent)
Recommendation: STRONG BUY
SL Distance: 15-30 pts (based on 13.5 score)
TP Distance: 22-45 pts (1.5x SL for 2:1 R:R)
```

---

## Trading Implications

### Golden Cross on 15m + 5m + Price at SMA Magnets
**Strongest Signal** → Highest Confluence Score
- Multiple timeframe agreement
- Strong momentum shift
- Price clustering at magnet levels
- Action: **TAKE** (high probability)

### Golden Cross on 15m Only
**Medium Signal** → Moderate Confluence Score
- Some momentum shift
- Needs confirmation from lower TF
- Action: **WATCH/WAIT** for 5m confirmation

### Golden Cross but Price Far from Magnets
**Weak Signal** → Lower Confluence Score
- Momentum shift but not at key levels
- Low confluence (fewer magnet hits)
- Action: **SKIP** (low probability)

### Death Cross Detection
Same principle but for **SELL** signals on LONG setup (avoid) or
**CONFIRM** SHORT setups.

---

## Testing the System

### 1. Verify Cross Detection
```bash
python << 'EOF'
from src.analysis.context_analyzer import detect_sma_crosses

# Sample prices in uptrend
closes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
result = detect_sma_crosses(closes, [5, 20, 50])

print(f"Golden Cross: {result['golden_cross']}")
print(f"Death Cross: {result['death_cross']}")
print(f"Type: {result['cross_type']}")
print(f"SMAs: {result['smas']}")
EOF
```

### 2. Run Agent and Check Alert Data
```bash
# Reset & run
rm -f src/trading/trades.db
python src/core/run.py

# Check database or Discord for cross info
```

### 3. Verify Magnet Scoring
```bash
python << 'EOF'
from src.analysis.context_analyzer import compute_intraday_sma_levels
from src.data.data_fetcher import MultiTimeframeFetcher

fetcher = MultiTimeframeFetcher()
bars_15m = fetcher.get_bars("MNQ", "15m", limit=100)
current_price = bars_15m[-1]["close"]

intraday = compute_intraday_sma_levels(bars_15m, current_price, "15m")

print(f"Magnet Score: {intraday['magnet_score']}")
print(f"Crosses: {intraday['crosses']}")
print(f"Nearest SMA: {intraday['nearest_sma']}")
print(f"Hits: {len(intraday['hits'])} magnet levels")
EOF
```

---

## Key Changes Summary

| Aspect | Before | After |
|--------|--------|-------|
| 15m Trend | Simple close > SMA | Golden/Death Cross detection |
| 5m Trend | Simple close > SMA | Golden/Death Cross detection |
| 15m Scoring | Trend only (+1) | Trend + SMA magnets + Crosses |
| 5m Scoring | Trend only (+1) | Trend + SMA magnets + Crosses |
| Confluence Max | ~8 points | ~15+ points (much clearer signals) |
| Filtering | Medium | High (bad setups filtered out) |

---

## Result

**Much stronger confluence scoring** with:
- ✅ Multiple SMA levels acting as magnet support/resistance
- ✅ Golden Cross / Death Cross momentum confirmation
- ✅ Clearer trend signals with multiple timeframe agreement
- ✅ Better filtering of low-quality setups
- ✅ Higher confluence = better risk/reward in TP/SL estimates

🚀 **Ready to test the new system!**
