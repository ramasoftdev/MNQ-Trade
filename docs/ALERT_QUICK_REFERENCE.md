# Alert Management — Quick Reference Card

## One-Liner Commands

### View Alerts
```bash
python -m src.trading.fill_trade --list-pending
```
Shows all alerts grouped by: NOT TAKEN | TAKEN (with SL/TP) | FILLED

---

## Taking Alerts

### Mark as TAKEN (Auto SL/TP)
```bash
python -m src.trading.fill_trade --alert-id=42 --take
```
✅ System calculates SL/TP based on confluence score

### Mark as TAKEN (Custom SL/TP)
```bash
python -m src.trading.fill_trade --alert-id=42 --take --stop-loss=30420.00 --take-profit=30480.00
```
✅ Use your own SL/TP instead of auto-calculated

---

## Adjusting SL/TP

### Update Only SL
```bash
python -m src.trading.fill_trade --alert-id=42 --update-sl=30430.00
```
✅ Keep existing TP, only change SL

### Update Only TP
```bash
python -m src.trading.fill_trade --alert-id=42 --update-tp=30490.00
```
✅ Keep existing SL, only change TP

### Update Both SL & TP
```bash
python -m src.trading.fill_trade --alert-id=42 --update-sl=30430.00 --update-tp=30490.00
```
✅ Change both at once

---

## Recording Fills (Exits)

### Basic (Exit Price Only)
```bash
python -m src.trading.fill_trade --alert-id=42 --exit-price=30475.00
```
✅ Uses current time, calculates P&L

### With Exit Time
```bash
python -m src.trading.fill_trade --alert-id=42 --exit-price=30475.00 --exit-time="14:35:30"
```
✅ Specify exact exit time

### With Notes
```bash
python -m src.trading.fill_trade --alert-id=42 --exit-price=30475.00 --notes="Hit TP at resistance"
```
✅ Add notes to the trade record

### Full Example
```bash
python -m src.trading.fill_trade --alert-id=42 --exit-price=30475.00 --exit-time="14:35:30" --notes="Scale out 1/2 position"
```

---

## Workflow Sequence

```
┌─────────────────────────────────────────────────────────────────┐
│  1. AGENT DETECTS SWEEP (automatic)                             │
│     → Alert auto-saved to DB, status = NOT TAKEN                │
│     → You review Discord notification                            │
└─────────────────────────────────────────────────────────────────┘

         ↓

┌─────────────────────────────────────────────────────────────────┐
│  2. YOU DECIDE: TAKE OR SKIP?                                   │
│                                                                  │
│  TAKE IT:                                                        │
│  $ python -m src.trading.fill_trade --alert-id=42 --take        │
│                                                                  │
│  Status changes to TAKEN, SL/TP set                             │
└─────────────────────────────────────────────────────────────────┘

         ↓ (optional: adjust SL/TP as trade moves)

┌─────────────────────────────────────────────────────────────────┐
│  3. OPTIONAL: ADJUST SL/TP MID-TRADE                            │
│                                                                  │
│  $ python -m src.trading.fill_trade --alert-id=42 --update-sl=30475.00
│                                                                  │
│  Use this any number of times as trade progresses              │
└─────────────────────────────────────────────────────────────────┘

         ↓ (when trade exits)

┌─────────────────────────────────────────────────────────────────┐
│  4. RECORD THE FILL (exit price)                                │
│                                                                  │
│  $ python -m src.trading.fill_trade --alert-id=42 --exit-price=30475.00
│                                                                  │
│  Status changes to FILLED, P&L calculated                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Real-World Example

**10:30 AM — Alert #42 Detected**
```
Agent sends alert: LONG @ 30450.50, Score 9.5, Assessment: TAKE
```

**10:35 AM — You Review & Take It**
```bash
python -m src.trading.fill_trade --alert-id=42 --take
# Output: Alert marked as TAKEN | SL: 30426.80 | TP: 30497.90
```

**10:50 AM — Price Moves Favorably, Tighten SL to Breakeven+5**
```bash
python -m src.trading.fill_trade --alert-id=42 --update-sl=30455.50
# Output: Alert 42 SL/TP updated | SL: 30455.50 | TP: 30497.90
```

**11:15 AM — Trade Hits Take Profit**
```bash
python -m src.trading.fill_trade --alert-id=42 --exit-price=30497.90 --notes="Hit TP"
# Output: Trade recorded: P&L=$949.00 (+0.155%), result=WIN
```

**11:20 AM — View Results**
```bash
python -m src.trading.fill_trade --list-pending

# Output shows:
# ✓ FILLED (1 trade):
#   ID   42 | LONG  | 30450.50 → 30497.90 | +$949.00 (+0.155%) ✓
```

---

## Alert Status Definitions

| Status | Meaning | Action Required |
|--------|---------|-----------------|
| **NOT TAKEN** | Alert generated, you haven't decided | Review and decide: `--take` or skip |
| **TAKEN** | You committed to trading it | Watch for entry/exit, can adjust SL/TP |
| **FILLED** | Trade is closed | ← End state, view P&L |

---

## Common Commands Cheatsheet

```bash
# View today's alerts
python -m src.trading.fill_trade --list-pending

# Take alert with auto SL/TP
python -m src.trading.fill_trade --alert-id=42 --take

# Take alert with custom SL/TP
python -m src.trading.fill_trade --alert-id=42 --take --stop-loss=30420 --take-profit=30480

# Tighten SL to breakeven
python -m src.trading.fill_trade --alert-id=42 --update-sl=30450.50

# Move TP higher (if winning)
python -m src.trading.fill_trade --alert-id=42 --update-tp=30510

# Record exit at SL
python -m src.trading.fill_trade --alert-id=42 --exit-price=30450.50 --notes="Stopped out"

# Record exit at TP
python -m src.trading.fill_trade --alert-id=42 --exit-price=30497.90 --notes="Hit target"

# Exit at different price with time
python -m src.trading.fill_trade --alert-id=42 --exit-price=30475.00 --exit-time="14:35:00"

# Generate daily report
python -m src.trading.fill_trade --report
```

---

## Tips

### ✅ DO
- Mark ALL taken alerts (even if you forget exit time initially)
- Use auto SL/TP for high-confluence setups
- Adjust SL to breakeven after profit is visible
- Record fills immediately for accurate P&L
- Review "NOT TAKEN" alerts weekly to improve decision-making

### ❌ DON'T
- Ignore alerts in Discord — review them all (even if you skip them)
- Leave alerts in limbo — mark taken or skip (don't partially decide)
- Override auto SL/TP just to get fewer losses (stick to plan)
- Forget to record fills — marks trade as pending forever
- Move TP tighter after taking a trade (let winners run)

---

## Python API (for code integration)

```python
from src.trading.trade_journal import TradeJournal

journal = TradeJournal()

# Take an alert
journal.mark_as_taken(alert_id=42)

# Take with custom SL/TP
journal.mark_as_taken(alert_id=42, stop_loss=30420.00, take_profit=30480.00)

# Update SL/TP
journal.update_sl_tp(alert_id=42, stop_loss=30430.00)

# Get alert details
alert = journal.get_alert(42)
print(f"Taken: {alert['taken']}, SL: {alert['stop_loss']}, TP: {alert['take_profit']}")

# Auto-calculate SL/TP
sl, tp = journal.calculate_sl_tp(30450.50, "LONG", 9.5, atr=20)
print(f"Auto SL: {sl}, Auto TP: {tp}")
```

---

## Troubleshooting

**Q: Alert not found?**
```bash
# Check you have the right ID
python -m src.trading.fill_trade --list-pending
# Find correct alert ID in output
```

**Q: Want to mark as NOT taken after marking as taken?**
```
Currently: Can only move forward (NOT TAKEN → TAKEN → FILLED)
Workaround: Use --list-pending to review, contact support to reset
```

**Q: Accidentally recorded wrong exit price?**
```
Currently: Must record exit; to "undo", open database directly
Workaround: Ask support to delete trades[id] row and reset alerts[id].trade_status = 'PENDING'
```

**Q: Auto SL/TP seems wrong?**
```
Check: 
- Is the default ATR=20 correct for today's volatility?
- Is your confluence_score accurate?
- Manual SL/TP: python -m src.trading.fill_trade --alert-id=42 --take --stop-loss=X --take-profit=Y
```

---

## Next: Integrate TopstepX API

Future: Auto-fill on API-side broker fills
```bash
# Upcoming: (not yet implemented)
python -m src.trading.fill_trade --enable-topstepx
# → Records exits automatically when Topstep confirms fills
```

---

**Print this card and keep it handy!**
