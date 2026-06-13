# Indicator System Update - Summary

## What Changed

### ❌ REMOVED
- **1H Timeframe** - No longer used
- **30m Timeframe** - No longer used
- **EMA (Exponential Moving Averages)** - Replaced with SMA

### ✅ ADDED
- **1D (Daily) Timeframe** - Higher timeframe trend confirmation
- **Multiple SMAs (Simple Moving Averages)** - For support/resistance magnet levels
- **Daily SMA Magnet Scoring** - Similar to SPY pivot magnet scoring

---

## New SMA Configuration

### Daily (1D) - Support/Resistance Levels
```
SMA(5)     - Fastest, recent trend
SMA(20)    - Short-term trend
SMA(50)    - Medium-term trend  
SMA(100)   - Long-term trend
SMA(200)   - Very long-term trend/trend
```

**Purpose**: Act as magnet levels for support/resistance
**Scoring**: Distance-based magnet effect (like SPY pivots)
- Very Close (< 3 pts):  +2.0 points
- Close (3-7 pts):        +1.0 points
- Medium (7-15 pts):      +0.5 points
- Far (> 15 pts):         +0.0 points

### 15m Timeframe - Trend Detection
```
SMA(5)     - Entry confirmation
SMA(20)    - Short-term trend
SMA(50)    - Medium-term trend
```

**Purpose**: Confirm sweep direction
**Logic**: If close > SMA(5) = BULL, else BEAR

### 5m Timeframe - Trend Detection
```
SMA(5)     - Entry confirmation
SMA(20)    - Short-term trend
SMA(50)    - Medium-term trend
```

**Purpose**: Ultra-short term confirmation
**Logic**: If close > SMA(5) = BULL, else BEAR

---

## How It Works

### 1. Daily SMA Magnet Scoring
When an alert is generated:
```
Current Price: 29,766.75

Daily SMA(5):    29,765.00  → Distance: 1.75 pts  → VERY CLOSE (+2.0)
Daily SMA(20):   29,750.00  → Distance: 16.75 pts → Far (0.0)
Daily SMA(50):   29,760.00  → Distance: 6.75 pts  → CLOSE (+1.0)
Daily SMA(100):  29,755.00  → Distance: 11.75 pts → MEDIUM (+0.5)
Daily SMA(200):  29,750.00  → Distance: 16.75 pts → Far (0.0)

DAILY SMA MAGNET SCORE = 2.0 + 1.0 + 0.5 = +3.5
```

### 2. Timeframe Alignment
```
1D Trend:   BULL (if close > SMA(5))
15m Trend:  BULL (if close > SMA(5))
5m Trend:   BULL (if close > SMA(5))

Alignment Check:
├─ 1D: BULL ✓
├─ 15m: BULL ✓
└─ 5m: BULL ✓

ALIGNMENT = 3 aligned (minimum required)
```

### 3. Total Confluence Score
```
Base Score:          5 points (sweep + conditions)
External Score:      2 points (SPY pivot near)
Daily SMA Score:     3.5 points (magnet levels)
─────────────────────────────────
TOTAL CONFLUENCE:   10.5 points

This drives:
├─ P&L ratio (0.5x to 2.0x multiplier)
├─ SL distance (15-30 pts)
└─ TP distance (1.5x SL distance for 2:1 R:R)
```

---

## Code Changes

### config.py
**Before:**
```python
EMA_PERIODS = {
    "1h":  50,
    "30m": 100,
    "15m": 100,
    "5m":  200,
}
```

**After:**
```python
SMA_PERIODS = {
    "1d":  [5, 20, 50, 100, 200],
    "15m": [5, 20, 50],
    "5m":  [5, 20, 50],
}

DAILY_SMA_MAGNET_PROXIMITY = 15  # Pts away to count as magnet
```

### context_analyzer.py
**Key Updates:**
1. Replaced `compute_ema()` with `compute_sma()`
2. Added `compute_sma_list()` for multiple SMAs
3. Added `compute_daily_sma_levels()` for magnet scoring
4. Updated `build_mtf_context()` to:
   - Use 1D bars instead of 1H
   - Calculate daily SMA magnet scores
   - Include daily SMA score in confluence
5. Updated timeframe references (1h → 1d, removed 30m)

---

## Alert Information Now Includes

```python
Alert {
    confluence_score: 10.5,    # Total (base + ext + daily_sma)
    base_score: 5,             # Conditions
    ext_score: 2,              # SPY/SPX
    daily_sma_score: 3.5,      # NEW: Daily SMA magnet
    
    daily_sma: {               # NEW: Daily SMA details
        smas: {
            "sma_5": 29765.00,
            "sma_20": 29750.00,
            "sma_50": 29760.00,
            "sma_100": 29755.00,
            "sma_200": 29750.00,
        },
        magnet_score: 3.5,
        nearest_sma: {
            "period": 5,
            "price": 29765.00,
            "distance": 1.75,
        },
        hits: [
            {"type": "daily_sma", "period": 5, "price": 29765.00, "distance": 1.75},
            {"type": "daily_sma", "period": 50, "price": 29760.00, "distance": 6.75},
            {"type": "daily_sma", "period": 100, "price": 29755.00, "distance": 11.75},
        ]
    }
}
```

---

## Why This is Better

✅ **Longer Context**: Daily SMAs show macro trend structure
✅ **Support/Resistance Zones**: Multiple SMAs act as magnet levels (like pivots)
✅ **Cleaner Trend Detection**: SMA is simpler & more reliable than EMA
✅ **Distance-Based Scoring**: Matches SPY pivot magnet approach
✅ **Better Risk/Reward**: Confluence score now includes institutional level alignment
✅ **Visual Clarity**: Easy to see on charts (SMA is standard indicator)

---

## Testing the Changes

### 1. Verify Configuration
```bash
python << 'EOF'
from src.data.config import SMA_PERIODS, TIMEFRAMES, DAILY_SMA_MAGNET_PROXIMITY

print("SMA Periods:", SMA_PERIODS)
print("Timeframes:", list(TIMEFRAMES.keys()))
print("Daily SMA Magnet Proximity:", DAILY_SMA_MAGNET_PROXIMITY)
EOF
```

Output should show:
```
SMA Periods: {'1d': [5, 20, 50, 100, 200], '15m': [5, 20, 50], '5m': [5, 20, 50]}
Timeframes: ['1d', '15m', '5m']
Daily SMA Magnet Proximity: 15
```

### 2. Test Daily SMA Calculation
```bash
python << 'EOF'
from src.analysis.context_analyzer import compute_daily_sma_levels
from src.data.data_fetcher import MultiTimeframeFetcher

fetcher = MultiTimeframeFetcher()
bars_1d = fetcher.get_bars("MNQ", "1d", limit=250)

current_price = bars_1d[-1]["close"]
daily_sma = compute_daily_sma_levels(bars_1d, current_price)

print(f"Current Price: {current_price:.2f}")
print(f"Daily SMAs: {daily_sma['smas']}")
print(f"Magnet Score: {daily_sma['magnet_score']}")
print(f"Nearest SMA: {daily_sma['nearest_sma']}")
EOF
```

### 3. Run Agent & Check Alerts
```bash
# Reset database first
rm -f src/trading/trades.db

# Run agent
python src/core/run.py

# Check next alert includes daily_sma data
```

---

## Before & After Example

### BEFORE (Old EMA System)
```
Alert triggered:
├─ Direction: LONG
├─ Base Score: 5 (sweep + conditions)
├─ Ext Score: 1 (SPY pivot)
├─ EMA(1H): 29,750.00 - Not used for scoring
├─ EMA(30m): 29,755.00 - Not used for scoring
└─ Total: 6 points
```

### AFTER (New SMA System)
```
Alert triggered:
├─ Direction: LONG
├─ Base Score: 5 (sweep + conditions)
├─ Ext Score: 1 (SPY pivot)
├─ Daily SMA Score: 3.5
│   ├─ SMA(5):   29,765.00 (1.75 pts away) → +2.0
│   ├─ SMA(50):  29,760.00 (6.75 pts away) → +1.0
│   └─ SMA(100): 29,755.00 (11.75 pts away) → +0.5
├─ 1D Trend: BULL (price > SMA(5))
├─ 15m Trend: BULL (confirmation)
├─ 5m Trend: BULL (confirmation)
└─ Total: 9.5 points (stronger signal!)
```

---

## Database Reset

The database was already emptied to start fresh with the new system. When you run the agent next:

```bash
rm -f src/trading/trades.db  # Start completely fresh
python src/core/run.py       # Builds new database with daily data
```

---

## Ready to Test?

The system is now configured with:
- ✅ 1D daily timeframe for macro trend
- ✅ 5 SMAs on daily for support/resistance magnet levels
- ✅ 3 SMAs on 15m/5m for trend confirmation
- ✅ Distance-based magnet scoring (like SPY pivots)
- ✅ Higher confluence scores from multi-level alignment

**Next Steps:**
1. Start the agent: `python src/core/run.py`
2. Wait for a sweep to trigger an alert
3. Check Discord and database for the new daily SMA scoring
4. Start monitor: `python src/monitoring/monitor.py`
5. Monitor exit detection with the new confluence system

Let me know if you see any issues or want to adjust the SMA periods! 🚀
