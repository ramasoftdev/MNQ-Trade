# Trade Journal & Daily Report — User Guide

## Overview

The MNQ Trading Agent now includes a complete **trade journal system** with:
- ✅ Automatic alert logging to SQLite
- ✅ Manual trade fill recording (entry/exit prices)
- ✅ Win/loss statistics and P&L tracking
- ✅ Daily report generation with Discord alerts
- ✅ Setup analysis by direction and confluence band

---

## Quick Start

### 1. Log Trades as They Execute

After getting an alert, record the exit price:

```bash
python fill_trade.py --alert-id=1 --exit-price=30450.50 --exit-time="14:35:00"
```

**Parameters:**
- `--alert-id`: ID from the Discord alert (or use `--list-pending` to find it)
- `--exit-price`: Price where trade exited (required)
- `--exit-time`: Exit time in HH:MM:SS format (optional, default: now)
- `--notes`: Optional notes about the trade

**Example with notes:**
```bash
python fill_trade.py --alert-id=1 --exit-price=30450.50 --notes="Hit resistance, stopped out"
```

### 2. View Pending & Filled Alerts

```bash
python fill_trade.py --list-pending
```

**Output:**
```
═════════════════════════════════════════════════════════════════════════
  PENDING & FILLED ALERTS — 2026-06-05
═════════════════════════════════════════════════════════════════════════

📋 PENDING (3 alerts waiting for fills):

  ID    1 | 14:30 | SHORT @ 30450.50 | Score 8.5 | TAKE
  ID    2 | 14:45 | LONG @ 30460.25  | Score 9.0 | TAKE
  ID    3 | 15:00 | SHORT @ 30445.00 | Score 7.5 | HOLD

✓ FILLED (2 alerts):

  ID    4 | LONG  | 30455.00 → 30465.00 | +$200.00 (+0.3%) ✓
  ID    5 | SHORT | 30450.00 → 30440.00 | +$200.00 (+0.3%) ✓
═════════════════════════════════════════════════════════════════════════
```

### 3. Generate Daily Report

```bash
python fill_trade.py --report
```

Or for a specific date:
```bash
python fill_trade.py --report "2026-06-05"
```

**Output:** Shows summary stats, breakdown by direction/confluence, and top trades

---

## How It Works

### Automatic Alert Logging

When the agent sends a Discord alert, it **automatically logs** to the trade journal:
- Alert timestamp
- Direction (LONG/SHORT)
- Entry price
- Confluence score and components
- Claude's assessment and probability
- All market context (VWAP, POC, SPY price, etc.)

**Alert is logged with status:** `PENDING` (waiting for fill)

### Manual Fill Recording

You run `fill_trade.py` with the exit price. The system:
1. Finds the alert by ID
2. Retrieves entry price and time from the database
3. Calculates P&L based on direction:
   - **LONG:** (exit_price - entry_price) × $20/pt
   - **SHORT:** (entry_price - exit_price) × $20/pt
4. Marks trade as WIN/LOSS
5. Updates alert status to `FILLED`

### Daily Reports

Every day at **4:05 PM CT** (market close), the agent automatically:
1. Aggregates all trades from the day
2. Calculates statistics (win rate, P&L, average confluence)
3. Generates a formatted Discord embed
4. Posts to Discord
5. Saves HTML archive for records

---

## Database Schema

### alerts table

Stores every sweep alert with full context:

```
id              — Unique alert ID
timestamp       — When alert fired
date            — Date (YYYY-MM-DD)
direction       — LONG or SHORT
entry_price     — MNQ price at alert
trigger_tf      — 15m or 5m
confluence_score— Total score (0-12+)
base_score      — Base conditions (0-7)
ext_score       — SPX/SPY bonus (0-3+)
spy_magnet_score— SPY pivot distance bonus
sweep_confirmed — Boolean: sweep confirmed
reversal_candle — Boolean: reversal candle
near_poc        — Boolean: price near POC
... (all conditions)
probability     — Claude's 0-100% estimate
assessment      — TAKE/HOLD/WATCH/PASS
confidence      — low/medium/high
reasoning       — Claude's explanation
trade_status    — PENDING → FILLED → CLOSED
created_at      — Auto timestamp
```

### trades table

Stores executed fills with P&L:

```
id              — Unique trade ID
alert_id        — FK to alerts table
entry_price     — Entry price (from alert)
entry_time      — Entry timestamp
exit_price      — Exit price (you provide)
exit_time       — Exit timestamp (you provide)
pnl             — Profit/loss in dollars
pnl_percent     — P&L as %
hold_seconds    — How long trade was held
result          — WIN / LOSS / BREAK_EVEN
notes           — Your notes
created_at      — When fill was recorded
```

---

## Statistics & Reports

### Daily Stats Include:

- **Total Alerts:** How many sweeps fired
- **Total Trades:** How many were executed
- **Win/Loss:** Count and percentage
- **P&L:** Total and average per trade
- **Confluence:** Average score of all alerts
- **By Direction:** LONG vs SHORT breakdown
- **By Score Band:** Performance of 10+, 8-10, 5-8, <5 setups

### Example Report

```
════════════════════════════════════════════════════════════════════════════
  MNQ TRADING AGENT — DAILY REPORT
  2026-06-05
════════════════════════════════════════════════════════════════════════════

SUMMARY
────────────────────────────────────────────────────────────────────────────
  Total Alerts:      8
  Total Trades:      6
  Wins / Losses:     4 / 2
  Win Rate:          66.7%
  Total P&L:         $650.00
  Avg P&L / Trade:   $108.33
  Avg Confluence:    8.5

PERFORMANCE BY DIRECTION
────────────────────────────────────────────────────────────────────────────
  LONG   — 3 trades, 3 wins, 100.0% WR, $600.00 P&L
  SHORT  — 3 trades, 1 wins, 33.3% WR, $50.00 P&L

PERFORMANCE BY CONFLUENCE SCORE
────────────────────────────────────────────────────────────────────────────
  10+  — 2 trades, 2 wins, 100.0% WR
  8-10 — 3 trades, 1 wins, 33.3% WR
  5-8  — 1 trades, 1 wins, 100.0% WR

TRADES DETAIL
────────────────────────────────────────────────────────────────────────────
  ✓ 14:30-14:45 | $30450.00 → $30460.00 | P&L: $200.00 (0.3%)
  ✓ 14:50-15:10 | $30465.00 → $30475.00 | P&L: $200.00 (0.3%)
  ✗ 15:20-15:35 | $30450.00 → $30460.00 | P&L: -$200.00 (-0.3%)
  ✓ 15:40-16:00 | $30455.00 → $30465.00 | P&L: $200.00 (0.3%)
  ✓ 16:05-16:20 | $30470.00 → $30475.00 | P&L: $100.00 (0.2%)
  ✗ 16:25-16:40 | $30450.00 → $30445.00 | P&L: -$100.00 (-0.2%)

════════════════════════════════════════════════════════════════════════════
Generated: 2026-06-05 16:05 CT
MNQ Trading Agent v2 — Daily Report
════════════════════════════════════════════════════════════════════════════
```

---

## CLI Commands Reference

### Record a Trade Fill

```bash
python fill_trade.py --alert-id=ID --exit-price=PRICE [--exit-time=TIME] [--notes=TEXT]
```

### List Pending Alerts

```bash
python fill_trade.py --list-pending
```

### Generate Report (Today)

```bash
python fill_trade.py --report
```

### Generate Report (Specific Date)

```bash
python fill_trade.py --report "2026-06-01"
```

---

## How the Daily Report Flows

```
1. Agent fires alert at 14:30
   ↓
2. Discord alert posted
   ↓
3. Alert auto-logged to trades.db with status=PENDING
   ↓
4. You execute trade and run:
   python fill_trade.py --alert-id=1 --exit-price=30460.50
   ↓
5. Fill recorded to trades table, alert status=FILLED
   ↓
6. Every minute, report scheduler checks if it's 4:05 PM
   ↓
7. At 4:05 PM, report generated from all day's trades
   ↓
8. Report formatted as Discord embed and posted
   ↓
9. HTML archive saved in ./reports/report_YYYY-MM-DD.html
```

---

## Integration with Agent

### Automatic Features

- ✅ Alerts auto-logged on Discord send
- ✅ Daily reports auto-generated at 4:05 PM CT
- ✅ Reports auto-posted to Discord
- ✅ No configuration needed

### Manual Workflow

```bash
# 1. Start agent
python agent.py

# 2. Monitor for alerts (they auto-log)

# 3. When you execute a trade, record it:
python fill_trade.py --alert-id=123 --exit-price=30450.50

# 4. View pending trades anytime:
python fill_trade.py --list-pending

# 5. Reports auto-generate at 4:05 PM, or generate on-demand:
python fill_trade.py --report
```

---

## File Locations

```
trades.db              ← SQLite database (auto-created)
reports/
  ├── report_2026-06-05.html
  ├── report_2026-06-04.html
  └── ...
```

**Database location:** Same directory as agent.py

**Reports location:** ./reports/ subdirectory (auto-created)

---

## Data Retention

All trades are kept forever in the database. You can:

- Query any date range
- View historical performance
- Analyze long-term statistics
- Archive HTML reports for record-keeping

---

## Troubleshooting

### Alert ID Not Found

```
Error: Alert 999 not found
```

**Solution:** Use `python fill_trade.py --list-pending` to find valid alert IDs from today.

### Time Format Error

```
Error: Invalid time format: 2:35 PM
```

**Solution:** Use 24-hour format: `--exit-time="14:35:00"`

### Database Locked

Usually temporary. Just retry the command. If persistent, check that agent.py isn't running multiple instances.

### Report Not Sending to Discord

Check that `DISCORD_WEBHOOK_URL` is set correctly in `.env` file.

---

## Next Steps

- ✅ **Trade Journal** — COMPLETE
- ✅ **Daily Reports** — COMPLETE  
- ⏳ TopstepX Trade Execution (auto-place orders)
- ⏳ Performance Dashboard (web UI)
- ⏳ Trade Journal Export (CSV/Excel)

---

**Version:** 1.0  
**Last Updated:** 2026-06-06  
**Components:** trade_journal.py, daily_report.py, fill_trade.py, report_scheduler.py
