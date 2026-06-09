# Historical Context Feedback Loop — Smart Alert Suggestions

## Overview

The agent now uses **2-week historical performance data** to make smarter alert suggestions.

```
Alert detected
   ↓
Check: Has this score band worked in the past 14 days?
   ├─ If 0-25% TP hit rate → Skip alert (bad setup)
   └─ If 25%+ TP hit rate → Continue
   ↓
Build Claude prompt WITH historical context
   ├─ "Score 9.5 alerts hit TP 75% in past 14 days"
   ├─ "LONG trades have 65% win rate this period"
   └─ "Use this to calibrate your probability"
   ↓
Claude gives probability (now informed by history)
   ↓
Send smarter alert
```

---

## Two-Part System

### Part 1: Pre-Filter (Option B)
**Before Claude is even called**, check if this score band has proven unprofitable.

```python
# In agent.py
if not _should_alert_on_sweep(confluence_score, direction):
    return  # Don't alert at all
```

**Rules:**
- **0% TP hit rate** → Skip alert entirely
- **< 25% TP hit rate** → Skip alert entirely  
- **< 40% TP hit rate** → Log warning, but continue
- **40%+ TP hit rate** → Safe to alert

**Why:** Avoid alerting on setups that historically lose.

### Part 2: Historical Context (Option A)
**With Claude**, add real data about how this score band has performed.

```python
# In agent.py
historical_context = _build_historical_context(score, direction)
ctx['historical_context'] = historical_context

# Claude receives:
# "Score 9.5 alerts: 75% TP hit, 25% SL hit"
# "LONG trades: 65% win rate"
# "Use this historical context to calibrate..."
```

**What Claude Sees:**
```
HISTORICAL PERFORMANCE (Last 14 days):

Score Band 9.5:
  Total alerts: 8
  Hit TP: 6 (75.0%)
  Hit SL: 2

Direction LONG:
  Total trades: 10
  Wins: 7 (70.0%)

Overall (last 14 days):
  Total trades: 27
  Win rate: 52.9%
  Total P&L: $4,250.50

GUIDANCE FOR THIS ALERT:
- If score band 9.5 historically hits TP 75%+, be confident
- If direction LONG has 70%+ win rate, favor it
- Factor this historical context into your probability assessment
```

**Why:** Claude can calibrate probabilities based on what actually works.

---

## How It Changes Alert Suggestions

### Before (No History)
```
Alert #100: Score 5.2 (low confluence)
Claude: "Weak setup, I see mixed signals"
Probability: 35%
Assessment: "WATCH"
```

### After (With History)
```
Alert #100: Score 5.2

PRE-FILTER CHECK:
  Score 5-8 band: 15% TP hit rate in last 14 days
  Decision: Skip alert (too risky)
  
  (Alert not sent at all)
```

OR (if allowed to continue):

```
Alert #100: Score 5.2

PRE-FILTER CHECK: 
  Score 5-8 band: 35% TP hit rate (borderline)
  Decision: Continue, but warn

Claude sees context:
  "Score 5-8 alerts: only 35% hit TP recently"
  
Claude: "This score band hasn't been working. Low confidence."
Probability: 18%
Assessment: "SKIP"
```

---

## Database Method: get_historical_stats()

**New method added to `TradeJournal`:**

```python
stats = journal.get_historical_stats(days=14)
```

**Returns:**

```python
{
    "period_days": 14,
    "period_start": "2026-05-22",
    "period_end": "2026-06-05",
    
    "by_score_band": {
        "10+": {
            "total": 8,
            "tp_hit": 6,
            "sl_hit": 2,
            "tp_rate": 75.0
        },
        "8-10": {
            "total": 10,
            "tp_hit": 5,
            "sl_hit": 5,
            "tp_rate": 50.0
        },
        "5-8": {
            "total": 6,
            "tp_hit": 1,
            "sl_hit": 5,
            "tp_rate": 16.7
        },
        "<5": {
            "total": 3,
            "tp_hit": 0,
            "sl_hit": 3,
            "tp_rate": 0.0
        }
    },
    
    "by_direction": {
        "LONG": {
            "total": 15,
            "wins": 10,
            "win_rate": 66.7
        },
        "SHORT": {
            "total": 12,
            "wins": 3,
            "win_rate": 25.0
        }
    },
    
    "overall": {
        "total_trades": 27,
        "total_wins": 13,
        "win_rate": 48.1,
        "total_pnl": 3245.50,
        "avg_pnl": 120.20
    }
}
```

---

## Helper Functions in agent.py

### _get_score_band(confluence_score)
Maps a confluence score to a band for grouping:
- `10+` → 10 or higher
- `8-10` → 8 to 9.99
- `5-8` → 5 to 7.99
- `<5` → Below 5

### _should_alert_on_sweep(confluence_score, direction)
**Pre-filter check (Option B)**

Returns `True` if alert should proceed, `False` if skipped.

Logic:
1. Get historical stats for last 14 days
2. Find this score band's TP hit rate
3. If 0%: return False (skip)
4. If < 25%: return False (skip)
5. If < 40%: return True (continue, but logged as weak)
6. Otherwise: return True

### _build_historical_context(confluence_score, direction)
**Context builder (Option A)**

Returns a formatted string with:
- Score band performance
- Direction performance
- Overall period stats
- Guidance for Claude

---

## Integration in Alert Flow

**In `on_bar_close()` callback:**

```python
def on_bar_close(tf: str, bars: list):
    # ... existing code ...
    
    # NEW: Check historical pre-filters
    if not _should_alert_on_sweep(ctx.get("confluence_score", 0), direction):
        log.info("Alert filtered out by historical pre-filter.")
        return  # STOP HERE, don't alert
    
    # ... build context ...
    
    # NEW: Add historical data to context
    historical_context = _build_historical_context(
        ctx.get('confluence_score', 0), 
        direction
    )
    ctx['historical_context'] = historical_context
    
    # Get Claude probability (Claude now sees historical data)
    prob = get_probability(ctx)
    
    # ... send alert ...
```

---

## Claude Prompt Changes

**In `probability_engine.py`:**

The historical context is now included in the prompt sent to Claude:

```python
return f"""... [existing prompt content] ...

{ctx.get('historical_context', '')}

Analyse this multi-timeframe setup. Weight 1H trend heavily — it defines the day's bias.
Use the historical performance data above to calibrate your probability assessment.
Return your assessment as JSON only."""
```

Claude now has **real data** about how this score band has performed.

---

## Real-World Example

### Scenario: You've been trading 2 weeks

**Historical data accumulated:**
```
Score 10+:  10 trades, 8 hit TP (80% success)
Score 8-10: 12 trades, 6 hit TP (50% success)
Score 5-8:  8 trades, 1 hit TP (12% success)
Score <5:   2 trades, 0 hit TP (0% success)

LONG direction: 16 trades, 11 wins (69%)
SHORT direction: 16 trades, 4 wins (25%)
```

### New Alert Arrives: Score 5.3 LONG

**Pre-filter (Option B):**
```
Score band 5-8: 12% TP hit rate
→ This band is terrible, skip
→ Alert NOT sent
```

**Result:**
You never see the alert. System learned: "Score 5-8 doesn't work for this trader"

---

### New Alert Arrives: Score 10.2 LONG

**Pre-filter (Option B):**
```
Score band 10+: 80% TP hit rate
→ This band is solid, continue
```

**Claude receives context (Option A):**
```
"Score band 10+: 8 TP hits out of 10 trades (80%)"
"Direction LONG: 11 wins out of 16 trades (69%)"
"Overall: 52% win rate in last 14 days"
```

**Claude:**
"This score band has been very reliable (80% TP hit). LONG direction strong (69%). This is a good setup."
**Probability:** 78% (informed by history)
**Assessment:** "TAKE"

---

## Benefits

✅ **Stop alerting on proven losers** — Pre-filter (Option B)  
✅ **Smarter Claude calibration** — Historical context (Option A)  
✅ **Learning system** — Each trade improves future alerts  
✅ **Feedback loop** — Your actual results shape alert suggestions  
✅ **Self-improving** — The more you trade, the smarter it gets  

---

## Time Window

**Fixed at 14 days** (2 weeks):
- Enough data to see patterns
- Recent enough to be relevant
- Adapts quickly to market changes
- Old trades gradually fall off

---

## What If There's No Data Yet?

**First few days:**
- `get_historical_stats()` returns empty data
- Pre-filter returns `True` (allow all)
- Context says "No trades recorded yet"
- Claude alerts as normal (no history to bias it)

**After first week:**
- You have some trades
- Score bands get TP rates
- Pre-filter starts filtering
- Context becomes meaningful

---

## Edge Cases

### Low Sample Size
If only 2 trades with score 9.5:
- Pre-filter still applies (0% or 100% rates possible with small samples)
- Claude sees small sample size and can be cautious
- As more trades accumulate, data becomes more reliable

### Direction Imbalance
If LONG has 80% win rate but SHORT has 20%:
- Claude sees both
- May bias toward LONG alerts
- This is intentional—learn from actual performance

### Score Band Boundaries
If score is exactly 8.00:
- Goes in "8-10" band
- Consistent with the _get_score_band() function

---

## Usage

The system is **automatic**. No action needed:

1. Just trade normally (mark alerts taken/skipped, record fills)
2. System accumulates 2 weeks of historical data
3. New alerts start using that data
4. Pre-filter skips bad setups automatically
5. Claude gets context to calibrate probabilities

---

## Verification

**Test the historical stats:**

```bash
cd /path/to/mnq_v2

python3 << 'EOF'
from src.trading.trade_journal import TradeJournal

journal = TradeJournal()
stats = journal.get_historical_stats(days=14)

print("Historical stats for last 14 days:")
print(f"Total trades: {stats['overall']['total_trades']}")
print(f"By score band: {stats['by_score_band']}")
print(f"By direction: {stats['by_direction']}")
EOF
```

---

## Summary

You now have a **self-improving trading system**:

1. **You trade** → System records results (TP hit or SL hit)
2. **System learns** → Accumulates 2 weeks of data
3. **System improves** → Uses data to filter and calibrate alerts
4. **You trade better** → Get fewer bad alerts, smarter suggestions

The more you trade, the smarter it gets. 🎯
