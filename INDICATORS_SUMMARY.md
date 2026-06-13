# Technical Indicators & Analysis Used

## Current Indicators Implemented

### 1. **EMA (Exponential Moving Average)**
- **File**: `src/analysis/context_analyzer.py:compute_ema()`
- **Purpose**: Trend detection across timeframes
- **Period**: Configurable (default: 50-period for trend)
- **Usage**: Determines if market is in BULL or BEAR trend
- **Timeframes**: 1H, 30m, 15m, 5m

### 2. **VWAP (Volume Weighted Average Price)**
- **File**: `src/analysis/context_analyzer.py:compute_vwap()`
- **Purpose**: Key confluence level
- **Anchored**: RTH session start
- **Bars Used**: 5-minute bars (most granular)
- **Scoring**: +1 if price near VWAP

### 3. **POC (Point of Control)**
- **File**: `src/analysis/context_analyzer.py:compute_poc()`
- **Purpose**: Volume profile analysis - where most volume traded
- **Sessions Tracked**: Last 3 Globex sessions
- **Bars Used**: 30-minute bars
- **Scoring**: +1 if price near POC

### 4. **Volume Profile & Volume Stats**
- **File**: `src/analysis/context_analyzer.py:compute_volume_stats()`
- **Metrics**:
  - Average volume over last N bars
  - Volume spike detection (> VOL_SPIKE_MULT * avg)
  - Current volume vs historical
- **Usage**: Identifies if sweep has strong volume confirmation

### 5. **Session Levels (Support/Resistance)**
- **File**: `src/analysis/context_analyzer.py:compute_session_levels()`
- **Types**:
  - Session Open (SO)
  - Session High (SH)
  - Session Low (SL)
  - Previous Day High/Low
- **Usage**: Entry points at institutional levels

### 6. **Liquidity Sweep Detection**
- **File**: `src/analysis/context_analyzer.py:detect_sweep()`
- **What It Does**:
  - Identifies when price touches session highs/lows
  - Detects if sweep is confirmed (wick beyond level)
  - Validates sweep across multiple timeframes
- **Scoring**: +2 base score if sweep confirmed

### 7. **Multi-Timeframe Trend Alignment**
- **File**: `src/analysis/context_analyzer.py:compute_all_trends()`
- **Timeframes**: 1H, 30m, 15m, 5m
- **Requirements**: 
  - Minimum 3 of 4 aligned for strong signal
  - 1H alignment is crucial (weighted more)
- **Scoring**: +1 for each additional aligned TF (up to +4)

### 8. **Reversal Candle Detection**
- **File**: `src/analysis/context_analyzer.py:build_mtf_context()`
- **Logic**: 
  - Checks if current candle shows reversal pattern
  - Bodysize, wicks, positioning relative to session levels
- **Scoring**: +0.5 if reversal pattern confirmed

### 9. **SPY Pivot Levels**
- **File**: `src/levels/spy_levels_analyzer.py`
- **Pivots Used**:
  - R1, R2, R3 (Resistance levels)
  - P (Pivot point)
  - S1, S2, S3 (Support levels)
- **Magnet Scoring**: 
  - Distance-based (closer = higher score)
  - Direction alignment bonus
- **Scoring**: Variable (up to +2 ext_score)

### 10. **RTH Session Detection**
- **File**: `src/analysis/context_analyzer.py:is_rth()`
- **Purpose**: Session context
- **Time**: 9:30 AM - 4:00 PM ET
- **Usage**: Different behavior for RTH vs pre-market/extended

---

## Indicator Configuration

**File**: `src/data/config.py`

```python
# Volume analysis
VOLUME_AVG_BARS = 20              # Bars to average volume
VOL_SPIKE_MULT = 1.5              # Volume spike multiplier

# Confluence thresholds
VWAP_PROXIMITY_PTS = 10           # How close to VWAP to count as hit
POC_PROXIMITY_PTS = 15            # How close to POC to count as hit
TICK_SIZE = 0.25                  # MNQ tick size

# Time periods
EMA_PERIODS = 50                  # EMA period for trend
NUM_SESSIONS = 4                  # Sessions to analyze
POC_SESSIONS = 3                  # Sessions for POC history

# Alignment & scoring
MIN_TF_ALIGNMENT = 3              # Minimum TFs that must align (out of 4)
SPY_PIVOT_DIRECTION_BONUS = 1.0   # Bonus if SPY pivot aligns with direction
```

---

## Scoring Breakdown Example

```
Base Score Calculation:
├─ Sweep Confirmed: +2
├─ VWAP Confluence: +1
├─ POC Confluence: +1
├─ Reversal Candle: +0.5
├─ TF Alignment Bonus:
│   ├─ 3 TFs aligned: +1
│   ├─ 4 TFs aligned: +2
│   └─ 1H + others: +1 extra
└─ Volume Spike: +1

External (SPY) Score:
├─ Pivot proximity: +0.5 to +2.0
├─ Direction alignment: +1.0
└─ Magnet effect scoring: distance-based

TOTAL CONFLUENCE SCORE: Base + Ext (typically 0-12+)
```

---

## Data Sources

**Market Data:**
- Source: Tradovate API (via ProjectX)
- Bars: 1H, 30m, 15m, 5m OHLCV
- Update: Real-time as bars close

**SPY Pivot Data:**
- Source: Manual file or Finnhub
- File: `src/levels/spx_pivots_YYYY-MM-DD.txt`
- Update: Daily

**Current Price:**
- Source: Finnhub API
- Symbol: MNQ
- Update: Real-time

---

## Missing / Could Add

### Not Yet Implemented:
- [ ] RSI (Relative Strength Index)
- [ ] MACD (Moving Average Convergence Divergence)
- [ ] Bollinger Bands
- [ ] Stochastic Oscillator
- [ ] ATR (Average True Range) - partially used in SL/TP
- [ ] Ichimoku Cloud
- [ ] Order Flow/Footprint
- [ ] Delta analysis
- [ ] Institutional Level Detection (beyond sweeps)

### Why Not Yet:
- Focus on **high-confluence setups** (sweeps + confluence)
- Indicator overload reduces signal quality
- Want to keep it **simple and tradeable**
- Current setup has been performing well

---

## How to Add New Indicators

If you want to add more indicators, here's the pattern:

### Step 1: Create indicator function
```python
# src/analysis/technical_indicators.py
def compute_rsi(bars: list, period: int = 14) -> float:
    """Compute RSI from price bars."""
    # Calculate RSI
    return rsi_value
```

### Step 2: Add to context builder
```python
# src/analysis/context_analyzer.py
rsi_value = compute_rsi(bars_5m)
ctx["rsi"] = rsi_value
```

### Step 3: Add to scoring logic
```python
# In build_mtf_context()
if rsi_value > 70:  # Overbought
    base_score += 0.5
elif rsi_value < 30:  # Oversold
    base_score += 0.5
```

### Step 4: Add to Discord output
```python
# src/reporting/discord_formatter.py
fields.append({"name": "RSI", "value": f"{rsi_value:.1f}"})
```

---

## Current Alert Factors (MVC View)

When an alert is created, these are saved:

```python
Alert(
    confluence_score,      # 0-12+ (main scoring metric)
    base_score,           # Count of confluences
    ext_score,            # SPY/external factor score
    spy_magnet_score,     # Distance-based SPY scoring
    
    # Conditions that contributed:
    sweep_confirmed,
    reversal_candle,
    near_poc,
    vwap_confluence,
    tf_1h_aligned,
    tf_3plus_aligned,
    rth_session,
    
    # Context data:
    current_vwap,
    current_poc,
    spy_price,
)
```

---

## Testing Indicators

```bash
# Test indicator calculations
python << 'EOF'
from src.analysis.context_analyzer import compute_ema, compute_vwap, compute_poc
from src.data.data_fetcher import MultiTimeframeFetcher

fetcher = MultiTimeframeFetcher()
bars_5m = fetcher.get_bars("MNQ", "5m", limit=50)

# Test EMA
ema = compute_ema([b.close for b in bars_5m], 50)
print(f"EMA(50): {ema:.2f}")

# Test VWAP
vwap = compute_vwap(bars_5m)
print(f"VWAP: {vwap:.2f}")

# Test POC
poc = compute_poc(bars_5m, "2026-06-12")
print(f"POC: {poc:.2f}")
