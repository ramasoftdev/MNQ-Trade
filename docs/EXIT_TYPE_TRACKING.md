# Exit Type Tracking — How Trades Actually Exited

## Overview

Now when you record a trade fill, the system automatically determines **HOW the trade exited**:

- **TP_HIT** — Trade reached take profit (strategy worked!)
- **SL_HIT** — Trade hit stop loss (setup was wrong)
- **MANUAL_EXIT** — You exited between SL and TP (manual decision)
- **BREAK_EVEN** — Trade exited at or near entry (no loss, no gain)

This is **critical** for analyzing which confluence scores actually work.

---

## Why This Matters

### Before (No Exit Type Tracking)
```
Alert #42: LONG @ 30450.50, Score 9.5

Trade exited @ 30498.00 → P&L: +$950 (WIN)

But... did it hit the TP we set?
Or did you exit manually?
You don't know!
```

### After (Exit Type Tracking)
```
Alert #42: LONG @ 30450.50, Score 9.5
SL: 30426.75, TP: 30498.00

Trade exited @ 30498.00 → P&L: +$950 (WIN) [TP_HIT]

Crystal clear: This setup hit its TP!
Can analyze which score bands hit TP most often
```

---

## Automatic Exit Type Detection

When you record a fill, the system compares exit price to SL/TP:

### For LONG Trades
```
Entry: 30450.50
SL: 30426.75 (below entry)
TP: 30498.00 (above entry)

Exit Price 30498.00 → TP_HIT      (reached TP)
Exit Price 30426.75 → SL_HIT      (hit SL)
Exit Price 30474.00 → MANUAL_EXIT (between SL and TP)
Exit Price 30450.50 → BREAK_EVEN  (at entry)
```

### For SHORT Trades
```
Entry: 30475.00
SL: 30490.00 (above entry)
TP: 30450.00 (below entry)

Exit Price 30450.00 → TP_HIT      (reached TP)
Exit Price 30490.00 → SL_HIT      (hit SL)
Exit Price 30465.00 → MANUAL_EXIT (between SL and TP)
Exit Price 30475.00 → BREAK_EVEN  (at entry)
```

---

## Usage

### When Recording a Fill

```bash
python -m src.trading.fill_trade --alert-id=42 --exit-price=30498.00
```

**Database stores:**
```
trades[42] = {
  exit_price: 30498.00
  exit_type: "TP_HIT"           ← Automatically determined!
  stop_loss_price: 30426.75
  take_profit_price: 30498.00
  pnl: 950.00
  result: "WIN"
}
```

### View Filled Trades with Exit Type

```bash
python -m src.trading.fill_trade --list-pending
```

**Output:**
```
✓ FILLED (5 trades):
  ID   38 | LONG  | 30425.50 → 30445.75 | +$210.00 ✓ 📍 TP_HIT
  ID   39 | SHORT | 30465.00 → 30450.25 | +$295.00 ✓ 📍 TP_HIT
  ID   40 | LONG  | 30445.00 → 30440.25 | -$95.00  ✗ ⛔ SL_HIT
  ID   41 | LONG  | 30460.00 → 30462.50 | +$50.00  ✓ ✋ MANUAL_EXIT
  ID   42 | SHORT | 30510.00 → 30515.50 | -$110.00 ✗ ⛔ SL_HIT
```

---

## Exit Type Analysis

The most important feature: **Analyze which confluence scores actually hit TP**

### Command

```bash
python -m src.trading.fill_trade --exit-analysis "2026-06-05"
```

### Example Output

```
============================== EXIT TYPE ANALYSIS — 2026-06-05 ==============================

How did trades exit by confluence score band?

Band       Total    TP Hit    SL Hit    Manual       BE    TP Rate
---------------------------------------------
10+            5         4         0         1        0      80.0%
8-10           6         3         2         1        0      50.0%
5-8            4         1         2         1        0      25.0%
<5             3         0         3         0        0       0.0%

============================================================================================

Interpretation:
  TP Hit:     Trade reached take profit (strategy worked)
  SL Hit:     Trade hit stop loss (setup was wrong)
  Manual:     You exited manually (between SL and TP)
  BE:         Trade exited at breakeven
  TP Rate:    % of trades that hit TP (success rate)

Goal: High confluence (10+) should have 70%+ TP hit rate

============================================================================================
```

### What This Tells You

✅ **Score 10+: 80% hit TP** — This is working! (High confidence is correct)  
⚠️ **Score 8-10: 50% hit TP** — Medium confidence needs improvement  
❌ **Score 5-8: 25% hit TP** — Low scores are too loose, tighten criteria  
❌ **Score <5: 0% hit TP** — Don't trade these! Always hit SL  

---

## Real-World Example

### Day 1: Trading with Exit Type Tracking

```
10:30 — Alert #42 detected (LONG @ 30450.50, Score 9.5)
10:35 — Marked as taken
        SL: 30426.75, TP: 30498.00

11:00 — You adjust SL to breakeven+5: 30455.50

14:00 — Trade hits original TP: 30498.00
        Record exit: python -m src.trading.fill_trade --alert-id=42 --exit-price=30498.00

        Database records:
        exit_price: 30498.00
        exit_type: "TP_HIT"      ← Strategy worked!
        pnl: $950.00
        result: "WIN"

14:05 — Check results
        python -m src.trading.fill_trade --exit-analysis
        
        Output shows: Score 9.5 band hit TP 80% of the time
        → This confidence level is reliable!
```

---

## Python API

### Get Exit Type Stats

```python
from src.trading.trade_journal import TradeJournal

journal = TradeJournal()

# For specific date
stats = journal.get_exit_type_stats("2026-06-05")

# For date range
stats = journal.get_exit_type_stats(date_range=("2026-06-01", "2026-06-05"))

# All time
stats = journal.get_exit_type_stats()

# Example result
# {
#     "10+": {
#         "total": 5,
#         "tp_hit": 4,
#         "sl_hit": 0,
#         "manual_exit": 1,
#         "break_even": 0,
#         "tp_hit_rate": 80.0
#     },
#     ...
# }

for band, data in stats.items():
    print(f"Score {band}: {data['tp_hit_rate']}% hit TP")
```

---

## Database Schema

### New Columns in `trades` Table

| Column | Type | Purpose |
|--------|------|---------|
| `exit_type` | TEXT | TP_HIT, SL_HIT, MANUAL_EXIT, or BREAK_EVEN |
| `stop_loss_price` | REAL | SL that was set (for reference) |
| `take_profit_price` | REAL | TP that was set (for reference) |

### Example Trade Record

```
id: 1
alert_id: 42
entry_price: 30450.50
entry_time: 2026-06-05 10:30:15
exit_price: 30498.00
exit_time: 2026-06-05 14:00:45
pnl: 950.00
pnl_percent: 0.155
hold_seconds: 12630
result: WIN
exit_type: "TP_HIT"              ← NEW!
stop_loss_price: 30426.75        ← NEW!
take_profit_price: 30498.00      ← NEW!
```

---

## Exit Type Definitions

### TP_HIT
**Trade reached take profit**
- LONG: exit_price >= take_profit
- SHORT: exit_price <= take_profit
- Meaning: Your strategy worked! The confluence score was right.

### SL_HIT
**Trade hit stop loss**
- LONG: exit_price <= stop_loss
- SHORT: exit_price >= stop_loss
- Meaning: The setup was wrong. This confluence score didn't work.

### MANUAL_EXIT
**You exited manually between SL and TP**
- Exit is between SL and TP
- Meaning: You made a discretionary decision (took partial profit, cut loss early, etc.)

### BREAK_EVEN
**Trade exited at or near entry price**
- Within 0.25 points of entry
- Meaning: No profit, no loss. Setup didn't develop.

---

## Analysis Patterns

### Pattern 1: Confluence Score is Calibrated Correctly

```
Score 10+:  80% TP hit → This is right!
Score 9-10: 70% TP hit → This is right!
Score 8-9:  55% TP hit → Still decent
Score <8:   20% TP hit → Too loose
```

**Action:** Use 9+ scores confidently, tighten criteria below 8

### Pattern 2: Confluence Score is Too Loose

```
Score 10+:  30% TP hit → Something wrong with your TP calculation
Score 9-10: 20% TP hit → Your TP targets are too tight
```

**Action:** Widen TP targets or adjust how you calculate confluence

### Pattern 3: Confluence Score is Too Strict

```
Score 10+:  5% TP hit → You're filtering out good setups
Score 9-10: 2% TP hit → Too many filters
```

**Action:** Loosen confluence criteria, accept more alerts

---

## Weekly Analysis Workflow

### Monday-Friday: Take Alerts & Record Fills
```bash
python -m src.trading.fill_trade --list-pending
python -m src.trading.fill_trade --alert-id=42 --take
python -m src.trading.fill_trade --alert-id=42 --exit-price=30475.00
```

### Friday EOD: Review the Week
```bash
python -m src.trading.fill_trade --exit-analysis
```

**Review Questions:**
1. Which score bands hit TP most often? (That's your sweet spot)
2. Which bands always hit SL? (Stop trading these)
3. Is your TP setting working? (If TP hit rate < 50%, widen it)
4. Is your SL setting working? (If SL hit rate > 50%, tighten it)

### Next Week: Adjust Strategy
Based on exit type patterns, adjust:
- Confluence score thresholds
- SL/TP distances
- Which timeframes to trade
- Which direction (LONG vs SHORT) works better

---

## Common Scenarios

### Scenario 1: High Confluence Hits TP, Low Doesn't

```
Exit Type Analysis:
  10+: 80% TP hit rate
  8-10: 60% TP hit rate
  5-8: 25% TP hit rate
  <5: 0% TP hit rate

Insight: Your confluence score is working perfectly!
Action: Only trade 8+ (or 9+ for high conviction)
```

### Scenario 2: TP Not Being Hit Enough

```
Exit Type Analysis:
  10+: 40% TP hit rate
  8-10: 35% TP hit rate

Insight: Your TP targets are too tight
Action: Increase TP distance (widen from 1.5x to 2.0x ATR)
```

### Scenario 3: Too Many Manual Exits

```
Exit Type Analysis:
  MANUAL_EXIT: 60% of all exits
  TP_HIT: 20%
  SL_HIT: 20%

Insight: You're second-guessing your plan
Action: Stick to the original SL/TP, trust the system
```

---

## Tips

✅ **Review exit types weekly** — This is your trading journal's most valuable metric  
✅ **Don't manually exit** — If you set SL/TP, let them work (MANUAL_EXIT is a red flag)  
✅ **Adjust based on data** — If low-confidence setups always hit SL, stop trading them  
✅ **Look for patterns** — Direction, timeframe, day-of-week all matter  
✅ **Trust high-confidence** — If 10+ scores hit TP 70%+, trade more of them  

---

## SQL Queries

### TP Hit Rate by Confluence Band

```sql
SELECT
    CASE
        WHEN a.confluence_score >= 10 THEN '10+'
        WHEN a.confluence_score >= 8 THEN '8-10'
        WHEN a.confluence_score >= 5 THEN '5-8'
        ELSE '<5'
    END as band,
    COUNT(*) as total,
    SUM(CASE WHEN t.exit_type = 'TP_HIT' THEN 1 ELSE 0 END) as tp_hits,
    ROUND(SUM(CASE WHEN t.exit_type = 'TP_HIT' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as tp_rate
FROM trades t
JOIN alerts a ON t.alert_id = a.id
WHERE a.date BETWEEN '2026-06-01' AND '2026-06-05'
GROUP BY band
ORDER BY confluence_score DESC;
```

### Most Profitable Exit Type

```sql
SELECT
    t.exit_type,
    COUNT(*) as trades,
    ROUND(SUM(t.pnl), 2) as total_pnl,
    ROUND(AVG(t.pnl), 2) as avg_pnl
FROM trades t
GROUP BY t.exit_type
ORDER BY total_pnl DESC;
```

### Win Rate by Exit Type

```sql
SELECT
    t.exit_type,
    COUNT(*) as trades,
    SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as wins,
    ROUND(SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate
FROM trades t
GROUP BY t.exit_type;
```

---

## Summary

Exit type tracking gives you **exact insight** into which confluence scores work:

| Metric | What It Shows | Action |
|--------|---------------|--------|
| TP_HIT % | Your strategy is working | Trade more of this score band |
| SL_HIT % | Setup criteria are wrong | Tighten filters or skip these |
| MANUAL_EXIT % | You lack discipline | Stick to SL/TP, don't override |
| BREAK_EVEN % | Setup didn't develop | May need better entry timing |

**Use this data every week to refine your trading edge!**
