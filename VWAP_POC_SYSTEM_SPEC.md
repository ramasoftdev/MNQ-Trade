# MNQ Trading Agent v3 — VWAP/POC System Specification

**Status:** Production (Phase 1-2-3 Complete)  
**Last Updated:** 2026-06-20  
**Entry Point:** `python src/core/run.py`

---

## 1. System Overview

The VWAP/POC system generates trading alerts based on:
- **Primary Signal:** 5-minute VWAP bounce detection
- **Confirmation:** 15-minute Moving Average alignment
- **Context:** Daily MA levels for macro analysis
- **Filtering:** Claude AI probability assessment

**Target:** 2-5 alerts/day with 55-60% win rate

---

## 2. Entry Logic

### 2.1 VWAP Bounce Detection (5m)

**Trigger Condition:**
- Price touches/crosses VWAP
- Current bar forms reversal candle (body ≥50% of range)
- Price reverses in entry direction

**LONG Bounce:**
```
Previous bar: low <= VWAP
Current bar:  close > open (bullish)
             current_price > VWAP
             Body size / Range > 0.5
```

**SHORT Bounce:**
```
Previous bar: high >= VWAP
Current bar:  close < open (bearish)
             current_price < VWAP
             Body size / Range > 0.5
```

### 2.2 Moving Average Confirmation (15m)

**Bullish Confirmation (for LONG):**
```
MA5 > MA20 > MA50
Direction bonus: +distance between MAs
```

**Bearish Confirmation (for SHORT):**
```
MA5 < MA20 < MA50
Direction bonus: +distance between MAs
```

### 2.3 Volume Confirmation

**Spike Detection:**
- Current volume > average volume × 1.2
- 5-bar lookback for average
- Adds +2 pts to confluence score if present

---

## 3. Confluence Scoring

**Maximum:** 10 points  
**Alert Threshold:** ≥ 6 points

### Breakdown:

| Component | Points | Condition |
|-----------|--------|-----------|
| VWAP Bounce | +3 | Primary entry signal detected |
| 15m MA Aligned | +2 | MAs confirmed in entry direction |
| Volume Spike | +0 to +2 | Ratio > 1.2x = +2, else +1 |
| POC Proximity | +1 | Price within 5 pts of POC |
| MA5 Proximity | +1 | Price within 5 pts of 15m MA5 |
| **Total** | **10** | **Maximum possible** |

### Example Scores:
- 6 pts: VWAP + MA + weak volume + POC
- 7 pts: VWAP + MA + volume spike + MA5 proximity
- 8 pts: VWAP + MA + volume spike + POC + MA5 proximity

---

## 4. Target & Stop Loss Calculation

**Based on Daily Moving Averages:**

### LONG Entry:
```
Stop Loss:   daily_ma50 - 5 pts (major support below)
Take Profit: daily_ma5 + 5 pts (daily resistance above)
Risk:Reward: 1:1+ ratio
```

### SHORT Entry:
```
Stop Loss:   daily_ma50 + 5 pts (major resistance above)
Take Profit: daily_ma5 - 5 pts (daily support below)
Risk:Reward: 1:1+ ratio
```

---

## 5. Claude Probability Filter

**Input to Claude:**
- Direction (LONG/SHORT)
- Entry price
- Stop loss & Take profit
- Confluence score (0-10)
- VWAP levels (5m, 15m)
- Daily MA context
- Macro trend (bullish/bearish/ranging)

**Output Assessment:**
- Probability: 0-100%
- Confidence: LOW / MEDIUM / HIGH
- Assessment: ALERT / SKIP / REVIEW
- Reasoning: Brief explanation

**Decision Logic:**
- If assessment = "SKIP" → alert filtered out
- Otherwise → alert created and sent to Discord

---

## 6. Daily MA Context

**For Macro Analysis:**

```
daily_mas = {
  "ma5": price_level,
  "ma20": price_level,
  "ma50": price_level
}

alignment = "bullish" | "bearish" | "none"
strength  = "strong" | "medium" | "weak"
trend     = "STRONG_UPTREND" | "WEAK_UPTREND" | 
            "STRONG_DOWNTREND" | "WEAK_DOWNTREND" | "RANGING"

price_position = "above_all" | "between_5_20" | 
                 "between_20_50" | "below_all"
```

---

## 7. Alert Generation

### 7.1 Alert Criteria (All Must Pass)

1. ✅ 5m VWAP bounce detected
2. ✅ 15m MAs aligned in entry direction
3. ✅ Confluence score ≥ 6/10
4. ✅ Cooldown not active (300 sec per direction)
5. ✅ Claude assessment ≠ "skip"

### 7.2 Alert Data Stored

```python
alert = {
  "timestamp": datetime,
  "direction": "LONG" | "SHORT",
  "current_price": float,
  "stop_loss": float,
  "take_profit": float,
  "confluence_score": int (0-10),
  "trigger_tf": "5m",
  "conditions": {
    "vwap_bounce": bool,
    "ma_aligned": bool,
    "volume_spike": bool
  },
  "vwap": float (5m VWAP),
  "poc": float,
  "probability": int (0-100),
  "confidence": str,
  "assessment": str,
  "daily_context": dict
}
```

---

## 8. Monitoring & Exit Tracking

### 8.1 Monitor Process

Runs separately: `python src/monitoring/monitor.py`

**Responsibilities:**
- Poll current MNQ price every 10-30 seconds
- Compare against pending alert SL/TP levels
- Auto-record exits when levels hit
- Send Discord notifications

### 8.2 Exit Types

- **TP_HIT:** Take profit level reached → WIN
- **SL_HIT:** Stop loss level reached → LOSS
- **MANUAL:** Closed manually by trader

---

## 9. Configuration

**Location:** `src/data/config.py`

### Key Settings:

```python
# Alert generation
CONFLUENCE_THRESHOLD = 6       # Minimum score for alert
CONFLUENCE_MAX = 10            # Maximum possible score
ALERT_COOLDOWN_SECS = 300      # 5 min between alerts per direction

# Timeframes
TIMEFRAMES = {
    "1d":  {"elementSize": 1440, "maxlen": 250},
    "15m": {"elementSize": 15,   "maxlen": 2000},
    "5m":  {"elementSize": 5,    "maxlen": 3000},
}

# MA Periods
MA_PERIODS = {
    "5m":  [5, 20, 50],
    "15m": [5, 20, 50],
    "1d":  [5, 20, 50]
}

# VWAP Settings
VWAP_TOLERANCE_PTS = 5.0
VWAP_REVERSAL_BODY_RATIO = 0.5

# Volume Settings
VOLUME_SPIKE_MULTIPLIER = 1.2
VOLUME_LOOKBACK_BARS = 5
```

---

## 10. Running the System

### 10.1 Start Agent

```bash
python src/core/run.py
```

**Expected Output:**
```
======================================================================
  MNQ Trading Agent v3 — VWAP/POC System
  Entry: 5m VWAP bounce + 15m MA confirmation
  Confluence threshold: 6/10 pts
======================================================================

Waiting for initial bar buffers to fill...
All timeframe buffers ready. Monitoring for VWAP bounces...
```

### 10.2 Start Monitor (Separate Terminal)

```bash
python src/monitoring/monitor.py --discord-off
```

### 10.3 Enable Discord Messages

```bash
python src/monitoring/monitor.py
```

---

## 11. File Structure

### Core Agent Files:
- `src/core/agent.py` — Main agent (VWAP/POC v3)
- `src/core/run.py` — Entry point
- `src/monitoring/monitor.py` — Exit tracking

### Analysis Modules:
- `src/analysis/vwap_analyzer.py` — VWAP bounce detection
- `src/analysis/ma_analyzer.py` — MA analysis & alignment
- `src/analysis/volume_analyzer.py` — Volume & POC
- `src/analysis/probability_engine.py` — Claude AI filtering

### Data & Services:
- `src/data/data_fetcher.py` — ProjectX/TopstepX API
- `src/data/config.py` — Configuration
- `src/data/spy_fetcher.py` — SPY context data

### Database & MVC:
- `src/database/alert_db.py` — Alert storage
- `src/database/trade_db.py` — Trade tracking
- `src/controllers/` — Business logic
- `src/views/discord_view.py` — Discord integration

---

## 12. Performance Targets

| Metric | Target | Achieved |
|--------|--------|----------|
| Alerts/day | 2-5 | Validating |
| Win rate | 55-60% | Validating |
| Confluence avg | 7.0 | Validating |
| False alerts | <30% | Validating |

---

## 13. Known Limitations

1. Requires ProjectX/TopstepX API access
2. MNQ contract must be available
3. Daily bars need 50+ days for full context
4. Claude API rate limits apply
5. Discord webhook URL required for notifications

---

## 14. Troubleshooting

### No Alerts Generated
- ✅ Check confluence threshold not too high
- ✅ Verify 15m MAs are calculating correctly
- ✅ Ensure volume spikes are being detected
- ✅ Check Claude assessment isn't filtering all

### High False Alert Rate
- 📈 Increase CONFLUENCE_THRESHOLD
- 📈 Adjust VWAP_REVERSAL_BODY_RATIO
- 📈 Raise VOLUME_SPIKE_MULTIPLIER

### Price Service Errors
- ✅ Verify FINNHUB_API_KEY in .env
- ✅ Check Finnhub service status
- ✅ Ensure network connectivity

---

**Version:** 3.0  
**System:** VWAP/POC Entry + MA Confirmation  
**Status:** Active Production
