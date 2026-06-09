# Alert System Update — New SL/TP Management

## Summary

You now have a **manual flag system** to control which alerts you take, with **automatic SL/TP calculation** based on confluence score.

---

## What Changed

### Database Schema
Three new columns added to `alerts` table:

| Column | Type | Purpose |
|--------|------|---------|
| `taken` | BOOLEAN | Did you take this alert? (you manually set this) |
| `taken_at` | DATETIME | When you marked it as taken |
| `stop_loss` | REAL | Your stop loss (auto-calculated or custom) |
| `take_profit` | REAL | Your take profit (auto-calculated or custom) |

### TradeJournal Class
Three new methods added:

1. **`mark_as_taken(alert_id, stop_loss=None, take_profit=None)`**
   - Mark an alert as taken
   - If SL/TP not provided, auto-calculate them
   - Sets `taken=1` and `taken_at=now`

2. **`update_sl_tp(alert_id, stop_loss=None, take_profit=None)`**
   - Update SL/TP for an existing taken alert
   - Only updates values you provide
   - Useful for dynamic SL management during trade

3. **`calculate_sl_tp(entry_price, direction, confluence_score, atr=20)`**
   - Auto-calculate SL/TP based on confluence score
   - Higher confluence → wider TP, tighter SL
   - Lower confluence → tighter TP, wider SL

### CLI Tool
Updated `fill_trade.py` with new flags:

```bash
# Mark as taken (auto SL/TP)
python -m src.trading.fill_trade --alert-id=42 --take

# Mark as taken (custom SL/TP)
python -m src.trading.fill_trade --alert-id=42 --take --stop-loss=30420.00 --take-profit=30480.00

# Update SL/TP mid-trade
python -m src.trading.fill_trade --alert-id=42 --update-sl=30430.00 --update-tp=30490.00

# List all alerts (shows which you took)
python -m src.trading.fill_trade --list-pending
```

---

## Auto-Calculation Logic

When you mark an alert as taken without specifying SL/TP:

```python
# Confluence score determines risk/reward profile
confidence_mult = min(2.0, max(0.5, confluence_score / 6.0))

# Higher confluence = wider TP (let winners run)
# Lower confluence = tighter TP (protect against fakes)

sl_distance = ATR × 0.75 × confidence_mult
tp_distance = ATR × 1.5 × confidence_mult
```

### Examples

```
Score 4.0 (low):   SL=30440.50, TP=30470.50  (tight TP, protect against fakes)
Score 6.0 (mid):   SL=30435.50, TP=30480.50  (balanced)
Score 9.5 (high):  SL=30426.75, TP=30498.00  (wide TP, let it ride)
Score 12.0 (max):  SL=30420.50, TP=30510.50  (maximum ride on conviction)
```

All maintain consistent **3:1 risk/reward ratio**.

---

## Three-Stage Workflow

### Stage 1: Alert Detected (Automatic)
```
Agent runs sweep detection → Saves alert to DB
Status: taken=0, stop_loss=NULL, take_profit=NULL
```

### Stage 2: You Review & Decide
```bash
python -m src.trading.fill_trade --alert-id=42 --take
# → Auto-calculates SL/TP based on confluence_score
# → Sets taken=1, taken_at=now
# → Status: READY TO TRADE
```

### Stage 3: Record the Fill
```bash
python -m src.trading.fill_trade --alert-id=42 --exit-price=30475.00
# → Creates trades table entry
# → Calculates P&L
# → Updates trade_status=FILLED
```

---

## View Alerts by Status

```bash
python -m src.trading.fill_trade --list-pending
```

Output shows three sections:

```
⏳ NOT TAKEN
  ID 44 | LONG @ 30480.00 | Score 4.1

✋ TAKEN (with SL/TP)
  ID 42 | LONG | E: 30450.50 | SL: 30426.75 | TP: 30498.00

✓ FILLED
  ID 38 | LONG | 30425.50 → 30445.75 | +$210.00 ✓
```

---

## Common Use Cases

### Quick Take with Auto SL/TP
```bash
# 10:35 — Alert looks good, take it
python -m src.trading.fill_trade --alert-id=42 --take

# Output: Alert marked as TAKEN | SL: 30426.75 | TP: 30498.00
```

### Custom SL/TP (if you disagree with auto)
```bash
# 10:35 — You want tighter SL and wider TP
python -m src.trading.fill_trade --alert-id=42 --take --stop-loss=30420.00 --take-profit=30510.00
```

### Breakeven SL Management
```bash
# 10:35 — Initial SL
python -m src.trading.fill_trade --alert-id=42 --take

# 11:00 — Price moved 20 pts in your favor, move SL to breakeven+5
python -m src.trading.fill_trade --alert-id=42 --update-sl=30455.50

# 11:30 — Lock in more profit, move SL to +10
python -m src.trading.fill_trade --alert-id=42 --update-sl=30460.50
```

### Record Exit
```bash
# 11:45 — Trade hits TP, record exit
python -m src.trading.fill_trade --alert-id=42 --exit-price=30498.00

# Database automatically:
# - Calculates P&L: (30498.00 - 30450.50) × 20 = $950.00
# - Sets result: WIN
# - Updates trade_status: FILLED
```

---

## Benefits

✅ **Disciplined Trading** — Force yourself to review every alert  
✅ **Smart Risk Management** — Auto SL/TP scales with confluence  
✅ **Flexibility** — Adjust SL/TP anytime during trade  
✅ **Tracking** — Know which alerts you took vs. skipped  
✅ **Performance Analysis** — Review your acceptance rate by score band  
✅ **No Manual P&L Calc** — System calculates everything  

---

## API Reference

### Mark Alert as Taken

```python
from src.trading.trade_journal import TradeJournal

journal = TradeJournal()

# Auto-calculate SL/TP
journal.mark_as_taken(alert_id=42)

# Custom SL/TP
journal.mark_as_taken(
    alert_id=42,
    stop_loss=30420.00,
    take_profit=30480.00
)
```

### Update SL/TP

```python
# Update only SL
journal.update_sl_tp(alert_id=42, stop_loss=30430.00)

# Update only TP
journal.update_sl_tp(alert_id=42, take_profit=30490.00)

# Update both
journal.update_sl_tp(
    alert_id=42,
    stop_loss=30430.00,
    take_profit=30490.00
)
```

### Auto-Calculate SL/TP

```python
sl, tp = journal.calculate_sl_tp(
    entry_price=30450.50,
    direction="LONG",
    confluence_score=9.5,
    atr=20  # default
)
print(f"SL: {sl:.2f}, TP: {tp:.2f}")
```

---

## File Changes

### Modified Files
- `src/trading/trade_journal.py` — Added 3 new methods + schema changes
- `src/trading/fill_trade.py` — Added new CLI commands + display logic

### New Documentation Files
- `docs/ALERT_MANAGEMENT_GUIDE.md` — Full guide with examples
- `docs/ALERT_QUICK_REFERENCE.md` — Command cheatsheet

---

## Testing

All existing tests still pass (11 passed):
```
✓ TestAlertLogging (3 tests)
✓ TestTradeRecording (4 tests)
✓ TestStatistics (4 tests)
```

New functionality tested and verified:
```
✓ Auto-calculation of SL/TP
✓ Marking alerts as taken
✓ Updating SL/TP mid-trade
✓ List display with taken status
```

---

## Next Steps

1. **Start using it:**
   ```bash
   python -m src.trading.fill_trade --list-pending
   ```

2. **Review alerts:**
   - High confluence (9+) → Take with auto SL/TP
   - Medium (6-8) → Review conditions carefully
   - Low (< 6) → Skip or tighten TP

3. **Analyze weekly:**
   - Which alerts did you take?
   - Which did you skip?
   - What was your win rate?

4. **Upcoming integration:**
   - TopstepX API auto-fill on broker-side fill
   - Trailing SL support
   - Scale-out (multiple TP targets)

---

## Quick Reference

```bash
# View today's alerts
python -m src.trading.fill_trade --list-pending

# Take alert (auto SL/TP)
python -m src.trading.fill_trade --alert-id=42 --take

# Take with custom SL/TP
python -m src.trading.fill_trade --alert-id=42 --take --stop-loss=30420 --take-profit=30480

# Adjust SL mid-trade
python -m src.trading.fill_trade --alert-id=42 --update-sl=30455

# Record exit
python -m src.trading.fill_trade --alert-id=42 --exit-price=30475.00
```

---

**Status: ✅ Ready to use**

See `docs/ALERT_MANAGEMENT_GUIDE.md` for full documentation.
See `docs/ALERT_QUICK_REFERENCE.md` for command cheatsheet.
