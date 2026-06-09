# Alert Management with SL/TP — Complete Guide

## Overview

You now have a three-stage workflow for managing alerts:

```
┌──────────────────────────────────────┐
│  Stage 1: Alert Detected (auto)      │
│  ─────────────────────────────────   │
│  Agent finds sweep → saves to DB     │
│  Status: NOT TAKEN                   │
│  SL/TP: null (empty)                 │
└──────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  Stage 2: You Review & Decide        │
│  ─────────────────────────────────   │
│  You mark alert as TAKEN             │
│  Status: TAKEN                       │
│  SL/TP: Auto-calculated or custom    │
└──────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  Stage 3: Record the Fill            │
│  ─────────────────────────────────   │
│  Trade closes → you record exit      │
│  Status: FILLED                      │
│  P&L: Calculated automatically       │
└──────────────────────────────────────┘
```

---

## Database Schema Changes

### New Columns in `alerts` table

| Column | Type | Purpose |
|--------|------|---------|
| `taken` | BOOLEAN | Did you take this alert? (1=yes, 0=no) |
| `taken_at` | DATETIME | When you marked it as taken |
| `stop_loss` | REAL | Your stop loss price |
| `take_profit` | REAL | Your take profit price |

### Example Alert Record

**Before (Just Detected):**
```
id: 42
direction: LONG
entry_price: 30450.50
confluence_score: 9.5
taken: 0 (false)
taken_at: NULL
stop_loss: NULL
take_profit: NULL
trade_status: PENDING
```

**After (You Take It):**
```
id: 42
direction: LONG
entry_price: 30450.50
confluence_score: 9.5
taken: 1 (true)
taken_at: 2026-06-05 10:45:30
stop_loss: 30435.50
take_profit: 30472.75
trade_status: PENDING
```

---

## SL/TP Auto-Calculation Logic

When you mark an alert as taken without specifying SL/TP, the system calculates them automatically:

### Formula

```python
# Normalize confluence score to multiplier (0.5x to 2.0x)
# Low score (4) = 0.5x ATR
# High score (12+) = 2.0x ATR

confidence_mult = min(2.0, max(0.5, confluence_score / 6.0))

sl_distance = ATR × 0.75 × confidence_mult
tp_distance = ATR × 1.5 × confidence_mult

# For LONG trades:
SL = entry - sl_distance
TP = entry + tp_distance

# For SHORT trades:
SL = entry + sl_distance
TP = entry - tp_distance
```

### Examples

**High Confluence (9.5):**
```
Confluence: 9.5
Multiplier: 9.5 / 6.0 = 1.58x

ATR: 20 pts
SL distance: 20 × 0.75 × 1.58 = 23.7 pts
TP distance: 20 × 1.5 × 1.58 = 47.4 pts

LONG entry at 30450.50:
SL = 30450.50 - 23.7 = 30426.80
TP = 30450.50 + 47.4 = 30497.90
```

**Low Confluence (5.0):**
```
Confluence: 5.0
Multiplier: 5.0 / 6.0 = 0.83x

ATR: 20 pts
SL distance: 20 × 0.75 × 0.83 = 12.45 pts
TP distance: 20 × 1.5 × 0.83 = 24.9 pts

SHORT entry at 30460.00:
SL = 30460.00 + 12.45 = 30472.45
TP = 30460.00 - 24.9 = 30435.10
```

**Key Points:**
- ✅ Higher confluence = wider TP (ride winners), tighter SL (protect losers)
- ✅ Lower confluence = tighter TP (take profits early), wider SL (less conviction)
- ✅ Default ATR = 20 pts (can be customized)
- ✅ SL is always closer than TP (good risk/reward)

---

## CLI Commands

### 1. View All Alerts with Status

**Command:**
```bash
python -m src.trading.fill_trade --list-pending
```

**Output:**
```
================================================== ALERT STATUS — 2026-06-05 ==================================================

⏳ NOT TAKEN (3 alerts):

  ID   42 | 10:30 | LONG  @ 30450.50 | Score   9.5 | TAKE  
  ID   43 | 10:45 | SHORT @ 30475.25 | Score   8.2 | TAKE  
  ID   44 | 11:20 | LONG  @ 30480.00 | Score   7.1 | WATCH 

✋ TAKEN (2 alerts with SL/TP set):

  ID   38 | LONG  | E: 30425.50 | SL: 30410.25 | TP: 30445.75 | Score   9.2
  ID   39 | SHORT | E: 30465.00 | SL: 30480.50 | TP: 30440.00 | Score   8.7

✓ FILLED (3 trades closed):

  ID   35 | LONG  | 30420.00 → 30430.50 |     +$210.00 (+0.03%) ✓
  ID   36 | SHORT | 30470.00 → 30455.00 |     +$300.00 (+0.05%) ✓
  ID   37 | LONG  | 30445.00 → 30440.25 |     -$95.00 (-0.02%) ✗

==================================================================================================================
```

---

### 2. Mark an Alert as TAKEN (Auto-Calculate SL/TP)

**Command:**
```bash
python -m src.trading.fill_trade --alert-id=42 --take
```

**What happens:**
1. Fetches alert #42 details
2. Calculates SL/TP based on confluence score
3. Updates database
4. Sets `taken = 1`, `taken_at = now`

**Output:**
```
10:45:30  INFO     Alert marked as TAKEN | SL: 30426.80 | TP: 30497.90
✓ Alert marked as taken
```

---

### 3. Mark as TAKEN with Custom SL/TP

**Command:**
```bash
python -m src.trading.fill_trade --alert-id=42 --take --stop-loss=30420.00 --take-profit=30480.00
```

**What happens:**
1. Uses your custom SL/TP instead of auto-calculated
2. Updates database with your values
3. Sets `taken = 1`, `taken_at = now`

**Output:**
```
10:45:30  INFO     Alert marked as TAKEN | SL: 30420.00 | TP: 30480.00
✓ Alert marked as taken
```

---

### 4. Update SL/TP for Existing TAKEN Alert

**Command (Update Only SL):**
```bash
python -m src.trading.fill_trade --alert-id=42 --update-sl=30430.00
```

**Command (Update Only TP):**
```bash
python -m src.trading.fill_trade --alert-id=42 --update-tp=30490.00
```

**Command (Update Both):**
```bash
python -m src.trading.fill_trade --alert-id=42 --update-sl=30430.00 --update-tp=30490.00
```

**What happens:**
1. Updates only the values you specify
2. Keeps existing values if not provided
3. Logs the new SL/TP

**Output:**
```
10:48:15  INFO     Alert 42 SL/TP updated | SL: 30430.00 | TP: 30490.00
✓ SL/TP updated
```

---

### 5. Record a Fill (Trade Exit)

**Command (Exit price only, uses now as time):**
```bash
python -m src.trading.fill_trade --alert-id=42 --exit-price=30472.00
```

**Command (With exit time):**
```bash
python -m src.trading.fill_trade --alert-id=42 --exit-price=30472.00 --exit-time="14:35:30"
```

**Command (With notes):**
```bash
python -m src.trading.fill_trade --alert-id=42 --exit-price=30472.00 --notes="Hit TP at resistance"
```

**What happens:**
1. Creates entry in `trades` table
2. Calculates P&L: `(exit - entry) × 20` for MNQ
3. Sets result: WIN, LOSS, or BREAK_EVEN
4. Updates alert: `trade_status = 'FILLED'`

**Output:**
```
14:35:31  INFO     Trade recorded: alert_id=42, direction=LONG, exit=30472.00, P&L=$430.00 (+0.070%), result=WIN
✓ Trade filled successfully
```

---

## Workflow Examples

### Example 1: Take Alert with Auto SL/TP

```bash
# 10:30 — Alert detected (auto-saved by agent)
# Alert #42 LONG @ 30450.50, Score 9.5

# 10:35 — You review and decide to take it
python -m src.trading.fill_trade --alert-id=42 --take

# Output:
# Alert marked as TAKEN | SL: 30426.80 | TP: 30497.90

# 10:50 — Trade exits at TP
python -m src.trading.fill_trade --alert-id=42 --exit-price=30497.90

# Database now shows:
# alerts[42].trade_status = 'FILLED'
# trades[42] = {entry: 30450.50, exit: 30497.90, pnl: $949.00, result: 'WIN'}
```

---

### Example 2: Take Alert, Adjust SL/TP Mid-Trade

```bash
# 10:30 — Alert detected
# Alert #43 SHORT @ 30475.25, Score 8.2

# 10:35 — Take with custom SL/TP
python -m src.trading.fill_trade --alert-id=43 --take --stop-loss=30490.00 --take-profit=30450.00

# 10:50 — Market moves, you want to tighten SL to breakeven
python -m src.trading.fill_trade --alert-id=43 --update-sl=30475.25

# 11:05 — Trade hits new SL at breakeven
python -m src.trading.fill_trade --alert-id=43 --exit-price=30475.25 --notes="Stopped at breakeven"

# Result: P&L = 0 (BREAK_EVEN)
```

---

### Example 3: Let Alert Expire (Don't Take It)

```bash
# 10:30 — Alert detected
# Alert #44 LONG @ 30480.00, Score 4.1 (low confluence)

# 14:00 — Market conditions changed, you don't take it
# ← Just don't call --take, alert stays in "NOT TAKEN" state

# View later:
python -m src.trading.fill_trade --list-pending

# Output shows:
# ⏳ NOT TAKEN (1 alerts):
#   ID   44 | 11:20 | LONG  @ 30480.00 | Score   4.1 | WATCH
```

---

## Python API

### In Your Code

```python
from src.trading.trade_journal import TradeJournal

journal = TradeJournal()

# Mark an alert as taken (auto-calculate SL/TP)
journal.mark_as_taken(alert_id=42)

# Mark as taken with custom SL/TP
journal.mark_as_taken(
    alert_id=42,
    stop_loss=30420.00,
    take_profit=30480.00
)

# Update SL/TP for existing taken alert
journal.update_sl_tp(
    alert_id=42,
    stop_loss=30430.00,
    take_profit=30490.00
)

# Auto-calculate SL/TP
sl, tp = journal.calculate_sl_tp(
    entry_price=30450.50,
    direction="LONG",
    confluence_score=9.5,
    atr=20
)
print(f"Auto SL: {sl}, Auto TP: {tp}")

# Get alert details (now includes taken, sl, tp)
alert = journal.get_alert(42)
print(f"Taken: {alert['taken']}")
print(f"SL: {alert['stop_loss']}")
print(f"TP: {alert['take_profit']}")
```

---

## Analysis & Reports

### Daily Report Now Includes Taken/Not Taken Breakdown

```bash
python -m src.trading.fill_trade --report "2026-06-05"
```

Expected output:
```
═══════════════════════════════════════════════════════════════
                    DAILY REPORT — 2026-06-05
═══════════════════════════════════════════════════════════════

📊 SUMMARY
──────────
Total Alerts:        8
  Not Taken:         2 (skipped, wrong setup)
  Taken:             6
  Filled:            5
  Pending:           1 (still open)

Trades Completed:    5
Wins:                3 (60%)
Losses:              2 (40%)
P&L:                 +$1,245.00
Avg Per Trade:       +$249.00

═══════════════════════════════════════════════════════════════
```

---

## Stats & Analytics

### Query Taken vs Not Taken

**SQL Query:**
```sql
SELECT 
    SUM(CASE WHEN taken = 1 THEN 1 ELSE 0 END) as taken_count,
    SUM(CASE WHEN taken = 0 THEN 1 ELSE 0 END) as skipped_count,
    COUNT(*) as total_alerts
FROM alerts
WHERE date = '2026-06-05';
```

**Python:**
```python
from src.trading.trade_journal import TradeJournal

journal = TradeJournal()
alerts = journal.get_alerts_by_date("2026-06-05")

taken = [a for a in alerts if a['taken']]
skipped = [a for a in alerts if not a['taken']]

print(f"Took {len(taken)} of {len(alerts)} alerts ({len(taken)/len(alerts)*100:.1f}%)")
print(f"Skipped {len(skipped)} alerts (bad setups)")
```

---

## Best Practices

### 1. Auto-Calculation is a Starting Point

```
✅ Good: Use auto-calculated SL/TP as a baseline
❌ Don't: Blindly follow auto values

High confluence (9+) → Can use auto SL/TP
Low confluence (4-6) → May want to adjust tighter TP
```

### 2. Adjust SL Dynamically

```bash
# Initial SL
python -m src.trading.fill_trade --alert-id=42 --take --stop-loss=30420.00

# 30 mins later, price favors you, move SL to breakeven+
python -m src.trading.fill_trade --alert-id=42 --update-sl=30450.50

# Later, tighten to lock in profits
python -m src.trading.fill_trade --alert-id=42 --update-sl=30475.00
```

### 3. Mark All Taken Alerts

```bash
# Even if you forget to record the exit that day, mark it taken
# So you know you were in it
python -m src.trading.fill_trade --alert-id=42 --take

# Later, when you exit:
python -m src.trading.fill_trade --alert-id=42 --exit-price=30472.00
```

### 4. Review "Not Taken" Alerts

```bash
# View your skipped alerts
python -m src.trading.fill_trade --list-pending

# Analyze why you skipped them
# Builds trading discipline and intuition
```

---

## Common Scenarios

### Scenario A: Take Low-Confluence Setup

```
Alert: LONG @ 30460.00, Score 4.1 (low)

# Auto-calc gives wide TP and SL
python -m src.trading.fill_trade --alert-id=44 --take
# SL: 30452.00, TP: 30472.00

# But you want tighter TP (less conviction)
python -m src.trading.fill_trade --alert-id=44 --update-tp=30468.00

# Record exit
python -m src.trading.fill_trade --alert-id=44 --exit-price=30468.00
```

---

### Scenario B: Scale Out (Multiple Exits)

*Current limitation: Single SL/TP per alert*

**Workaround:** Use notes field
```bash
python -m src.trading.fill_trade --alert-id=42 \
    --exit-price=30480.00 \
    --notes="1/2 position exited at TP; holding other half"
```

**Future Enhancement:** Support for multiple exit targets/scale-outs

---

### Scenario C: Breakeven SL Management

```bash
# Initial SL loose (protect against whipsaws)
python -m src.trading.fill_trade --alert-id=42 --take --stop-loss=30420.00

# After 15 mins, move to breakeven+5 pts
python -m src.trading.fill_trade --alert-id=42 --update-sl=30455.50

# Exit (worst case: small loss if wrong setup)
python -m src.trading.fill_trade --alert-id=42 --exit-price=30465.00
```

---

## Summary

| Stage | Manual Flag | Auto SL/TP | Action |
|-------|-------------|-----------|--------|
| **Detected** | `taken = 0` | NULL | Wait for your decision |
| **Taken** | `taken = 1` | Auto or custom | Ready to trade |
| **Filled** | `trade_status = FILLED` | Set at entry | P&L calculated |

---

## Next Steps

- ✅ Review each alert before taking it
- ✅ Use auto-calculated SL/TP as baseline
- ✅ Adjust mid-trade as conditions change
- ✅ Record fills to close out alerts
- ✅ Analyze weekly which alerts you take vs skip

**Future Enhancements:**
- [ ] Integration with TopstepX API for auto-fill on broker-side fill
- [ ] Scale-out support (multiple TP targets)
- [ ] Trailing SL (dynamic stop following price)
- [ ] Alert notifications to phone/email when SL/TP hit
