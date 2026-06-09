# Trade Storage System — Complete Guide

## Overview

The MNQ Trading Agent stores trades in a **SQLite database** with a two-stage workflow:

1. **Alert Stage** — When a sweep is detected, log the alert to `alerts` table
2. **Fill Stage** — When the trade is closed, record the exit in `trades` table and update alert status

---

## Database Location

```
src/trading/trades.db
```

SQLite file (portable, single-file database). Can be viewed with any SQLite browser.

---

## Database Schema

### Table 1: `alerts`

**Purpose:** Record every sweep alert detected by the agent.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER (PK) | Auto-increment alert ID |
| `timestamp` | DATETIME | When alert was detected |
| `date` | DATE | Date (for grouping by trading day) |
| `direction` | TEXT | "LONG" or "SHORT" |
| `entry_price` | REAL | Sweep entry level |
| `trigger_tf` | TEXT | "5m", "15m", "30m", or "1h" |
| `confluence_score` | REAL | Score 0-12+ |
| `base_score` | INTEGER | Core conditions met |
| `ext_score` | INTEGER | SPX/SPY bonus points |
| `spy_magnet_score` | REAL | SPY correlation score |
| `sweep_confirmed` | BOOLEAN | Sweep validated |
| `reversal_candle` | BOOLEAN | Reversal bar present |
| `near_poc` | BOOLEAN | Close to POC |
| `vwap_confluence` | BOOLEAN | Price near VWAP |
| `tf_1h_aligned` | BOOLEAN | 1H trend agrees |
| `tf_3plus_aligned` | BOOLEAN | 3+ timeframes aligned |
| `rth_session` | BOOLEAN | Regular trading hours |
| `current_vwap` | REAL | VWAP at alert time |
| `current_poc` | REAL | POC at alert time |
| `spy_price` | REAL | SPY price at alert time |
| `probability` | INTEGER | AI probability % |
| `assessment` | TEXT | "skip", "watch", or "take" |
| `confidence` | TEXT | "low", "medium", "high" |
| `reasoning` | TEXT | AI reasoning text |
| `trade_status` | TEXT | "PENDING" or "FILLED" |
| `created_at` | DATETIME | Record creation time |

**Example Alert Record:**
```
ID: 42
Timestamp: 2026-06-05 10:30:15
Date: 2026-06-05
Direction: LONG
Entry Price: 30450.50
Confluence Score: 9.5
Assessment: TAKE
Probability: 72%
Trade Status: PENDING ← waiting for fill
```

---

### Table 2: `trades`

**Purpose:** Record completed trades with P&L calculations.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER (PK) | Auto-increment trade ID |
| `alert_id` | INTEGER (FK) | Links to `alerts.id` |
| `entry_price` | REAL | Entry level (from alert) |
| `entry_time` | DATETIME | Entry timestamp (from alert) |
| `entry_ts` | REAL | Entry Unix timestamp |
| `exit_price` | REAL | Exit price (when filled) |
| `exit_time` | DATETIME | Exit timestamp (when filled) |
| `exit_ts` | REAL | Exit Unix timestamp |
| `pnl` | REAL | **Profit/Loss in dollars** |
| `pnl_percent` | REAL | P&L as percentage |
| `hold_seconds` | INTEGER | Duration in seconds |
| `result` | TEXT | "WIN", "LOSS", or "BREAK_EVEN" |
| `notes` | TEXT | Optional user notes |
| `created_at` | DATETIME | Record creation time |

**P&L Calculation:**
```
For LONG:  P&L = (exit_price - entry_price) × 20  (MNQ = $20/point)
For SHORT: P&L = (entry_price - exit_price) × 20
```

**Example Trade Record:**
```
Alert ID: 42
Entry: 30450.50 @ 10:30:15
Exit:  30460.75 @ 10:45:30
Hold: 15 minutes 15 seconds
Direction: LONG

P&L = (30460.75 - 30450.50) × 20 = $205.00 (+0.034%)
Result: WIN
```

---

### Table 3: `daily_stats`

**Purpose:** Cached daily performance summary (optional, for reports).

| Column | Type |
|--------|------|
| `date` | DATE (UNIQUE) |
| `total_alerts` | INTEGER |
| `total_trades` | INTEGER |
| `trades_won` | INTEGER |
| `trades_lost` | INTEGER |
| `total_pnl` | REAL |
| `win_rate_pct` | REAL |
| `avg_pnl` | REAL |
| `avg_confluence` | REAL |

---

## Two-Stage Workflow

### Stage 1: Alert Detected

When the agent detects a sweep setup:

```python
from src.trading.trade_journal import TradeJournal

journal = TradeJournal()

alert_data = {
    "timestamp": datetime.now(),
    "direction": "LONG",
    "current_price": 30450.50,
    "trigger_tf": "5m",
    "confluence_score": 9.5,
    "base_score": 7,
    "ext_score": 2.5,
    "probability": 72,
    "assessment": "TAKE",
    "conditions": {
        "sweep_confirmed": True,
        "reversal_candle": True,
        "near_poc": True,
        ...
    }
}

# Insert into alerts table, returns alert_id
alert_id = journal.log_alert(alert_data)
# Returns: 42
```

**Result:** New row in `alerts` table with `trade_status = 'PENDING'`

---

### Stage 2: Fill Recorded

When the trade is closed, record the exit:

**Using CLI:**
```bash
python -m src.trading.fill_trade --alert-id=42 --exit-price=30460.75 --exit-time="14:45:30"
```

**Using Python:**
```python
journal = TradeJournal()

journal.record_fill(
    alert_id=42,
    exit_price=30460.75,
    exit_time=datetime(2026, 6, 5, 14, 45, 30),
    notes="Hit TP at resistance"
)
```

**What happens:**
1. ✅ Fetches alert details (entry_price, entry_time, direction)
2. ✅ Calculates P&L: `(exit - entry) × 20` for LONG
3. ✅ Calculates hold_seconds
4. ✅ Determines result: "WIN" / "LOSS" / "BREAK_EVEN"
5. ✅ Inserts row into `trades` table
6. ✅ Updates alert: `trade_status = 'FILLED'`

**Result:**
```
trades table:
├─ alert_id: 42
├─ entry_price: 30450.50
├─ exit_price: 30460.75
├─ pnl: 205.00
├─ result: WIN
└─ hold_seconds: 915

alerts table (alert 42):
└─ trade_status: FILLED (changed from PENDING)
```

---

## Using TradeJournal in Code

### Log an Alert

```python
from src.trading.trade_journal import TradeJournal

journal = TradeJournal()

# Your alert context
alert_id = journal.log_alert({
    "timestamp": datetime.now(),
    "direction": "LONG",
    "current_price": 30450.50,
    "trigger_tf": "5m",
    "confluence_score": 9.5,
    "probability": 72,
    "assessment": "TAKE",
    # ... more fields ...
})

print(f"Alert logged with ID: {alert_id}")
```

### Record a Fill

```python
journal.record_fill(
    alert_id=alert_id,
    exit_price=30460.75,
    exit_time=datetime.now(),
    notes="Hit target"
)
```

### Retrieve Data

```python
# Get specific alert
alert = journal.get_alert(42)
print(alert["direction"])  # "LONG"
print(alert["confluence_score"])  # 9.5

# Get specific trade
trade = journal.get_trade(42)
print(trade["pnl"])  # 205.00
print(trade["result"])  # "WIN"

# Get all alerts for a date
alerts = journal.get_alerts_by_date("2026-06-05")
print(f"Total alerts: {len(alerts)}")

# Get all trades for a date
trades = journal.get_trades_by_date("2026-06-05")
print(f"Total trades: {len(trades)}")

# Get daily stats
stats = journal.get_daily_stats("2026-06-05")
print(f"Win rate: {stats['win_rate_pct']}%")
print(f"Total P&L: ${stats['total_pnl']}")

# Get date range stats
range_stats = journal.get_date_range_stats("2026-06-01", "2026-06-05")
print(f"5-day P&L: ${range_stats['total_pnl']}")

# Get setup analysis (by direction & score band)
setup_stats = journal.get_setup_stats("2026-06-05")
print(setup_stats["by_direction"])  # {"LONG": {...}, "SHORT": {...}}
print(setup_stats["by_score_band"])  # {"10+": {...}, "8-10": {...}, ...}
```

---

## CLI Commands

### Record a Fill

```bash
# Basic (exit_time defaults to now)
python -m src.trading.fill_trade --alert-id=42 --exit-price=30460.75

# With custom exit time
python -m src.trading.fill_trade --alert-id=42 --exit-price=30460.75 --exit-time="14:45:30"

# With notes
python -m src.trading.fill_trade --alert-id=42 --exit-price=30460.75 --notes="Hit TP at resistance"

# With datetime
python -m src.trading.fill_trade --alert-id=42 --exit-price=30460.75 --exit-time="2026-06-05 14:45:30"
```

### List Pending Alerts

```bash
python -m src.trading.fill_trade --list-pending
```

**Output:**
```
================================================================================
  PENDING & FILLED ALERTS — 2026-06-05
================================================================================

📋 PENDING (3 alerts waiting for fills):

  ID   42 | 10:30 | LONG  @ 30450.50 | Score 9.5 | TAKE
  ID   43 | 10:45 | SHORT @ 30475.25 | Score 8.2 | TAKE
  ID   44 | 11:20 | LONG  @ 30480.00 | Score 7.1 | WATCH

✓ FILLED (5 alerts):

  ID   38 | LONG  | 30425.50 → 30435.75 | +$205.00 (+0.034%) ✓
  ID   39 | SHORT | 30465.00 → 30450.25 | +$295.00 (+0.049%) ✓
  ID   40 | LONG  | 30445.00 → 30440.25 | -$95.00 (-0.016%) ✗
  ID   41 | LONG  | 30460.00 → 30462.50 | +$50.00 (+0.008%) ✓
  ID   37 | SHORT | 30510.00 → 30515.50 | -$110.00 (-0.018%) ✗

================================================================================
```

### Generate Report

```bash
# Today's report
python -m src.trading.fill_trade --report

# Specific date
python -m src.trading.fill_trade --report "2026-06-05"
```

---

## Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    AGENT RUNNING                             │
│  Detects sweep setup on 5m bar close                         │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  log_alert(context)    │
        │                        │
        │  Creates alert row     │
        │  with:                 │
        │  - entry_price         │
        │  - confluence_score    │
        │  - probability         │
        │  - assessment          │
        │  - trade_status=       │
        │    "PENDING"           │
        └────────┬───────────────┘
                 │
                 ▼
        ┌────────────────────────┐
        │  alerts table          │
        │  ─────────────────────│
        │  Alert #42:           │
        │  Direction: LONG      │
        │  Entry: 30450.50      │
        │  Status: PENDING ◄──┐ │
        │                    │ │
        │  Alert #43:        │ │
        │  Direction: SHORT  │ │
        │  Entry: 30475.25   │ │
        │  Status: PENDING ◄─┴─┤
        └────────────────────────┘
                 │
    ┌────────────┴──────────────┐
    │                           │
    ▼                           ▼
 Trader manually         (automatic in future)
 records exit price      when Topstep fills order
    │                           │
    └────────────────────┬──────┘
                         │
                         ▼
    ┌────────────────────────────────┐
    │ record_fill(alert_id, price)   │
    │                                │
    │ Fetches alert details          │
    │ Calculates P&L                 │
    │ Inserts trade row              │
    │ Updates alert status           │
    └────────────┬───────────────────┘
                 │
        ┌────────┴──────────────┐
        │                       │
        ▼                       ▼
    ┌──────────────┐    ┌──────────────────┐
    │ trades table │    │ alerts table     │
    │──────────────│    │──────────────────│
    │ Trade #42:   │    │ Alert #42:       │
    │ Entry: 30450 │    │ Status: FILLED ◄─┤
    │ Exit: 30460  │    │                  │
    │ P&L: +$205   │    │ (updated)        │
    │ Result: WIN  │    │                  │
    └──────────────┘    └──────────────────┘
         │                     │
         └─────────────┬───────┘
                       │
                       ▼
        ┌──────────────────────────┐
        │  daily_stats (cached)    │
        │                          │
        │  Date: 2026-06-05        │
        │  Total Alerts: 42        │
        │  Total Trades: 38        │
        │  Wins: 24 (63%)          │
        │  Total P&L: $4,850       │
        └──────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────┐
        │  Reports & Analytics     │
        │                          │
        │  Daily Report HTML       │
        │  Discord Summary         │
        │  Setup Analysis          │
        └──────────────────────────┘
```

---

## Example Workflow

### Day 1: 2026-06-05

**10:30 AM — Sweep Detected**
```python
# In agent.py, sweep detected on 5m bar
alert_id = journal.log_alert({
    "timestamp": datetime(2026, 6, 5, 10, 30, 15),
    "direction": "LONG",
    "current_price": 30450.50,
    "trigger_tf": "5m",
    "confluence_score": 9.5,
    "probability": 72,
    "assessment": "TAKE"
})
# Returns: alert_id = 42
# Database: alerts[42] inserted with trade_status = 'PENDING'
```

**10:45 AM — Trader Records Exit**
```bash
python -m src.trading.fill_trade --alert-id=42 --exit-price=30460.75 --notes="Hit TP"
```

**What happens:**
1. Fetch alert #42: entry=30450.50, entry_ts=...
2. Calculate P&L: (30460.75 - 30450.50) × 20 = $205.00
3. Calculate hold: 915 seconds (15m 15s)
4. Determine result: $205 > 0 → "WIN"
5. Insert into trades[42]
6. Update alerts[42].trade_status = 'FILLED'

**4:00 PM — Generate Daily Report**
```bash
python -m src.trading.fill_trade --report "2026-06-05"
```

**Query:**
```sql
SELECT
    COUNT(*) as total_alerts,
    SUM(CASE WHEN trade_status='FILLED' THEN 1 ELSE 0 END) as filled,
    SUM(pnl) as total_pnl
FROM alerts
WHERE date = '2026-06-05'
```

---

## Key Points

✅ **Two-phase design:** Alerts logged immediately, fills added later
✅ **Unique constraint:** Each alert can have only ONE trade (alert_id is UNIQUE in trades table)
✅ **P&L automatic:** Calculated when fill is recorded
✅ **Status tracking:** Easy to see PENDING vs FILLED alerts
✅ **Queryable:** SQLite is standard, can use any SQL tool
✅ **Portable:** Single .db file, can backup easily

---

## Future Enhancements

- [ ] **Auto-fill via TopstepX API:** When Topstep fills order, auto-record exit
- [ ] **CSV Export:** Export trades to Excel for external analysis
- [ ] **Streaks tracking:** Longest winning/losing streak
- [ ] **Setup heatmap:** Which setups (by score band) perform best
- [ ] **Time-of-day analysis:** Which hours yield best P&L
- [ ] **Multi-leg trades:** Support for pyramid trades or scale-outs

---

## Viewing the Database

**SQLite Browser (Free):**
- Download: https://sqlitebrowser.org/
- Open: `src/trading/trades.db`
- Browse tables, run custom queries

**Command Line:**
```bash
sqlite3 src/trading/trades.db

# View all alerts
SELECT id, timestamp, direction, entry_price, confluence_score, trade_status FROM alerts;

# View trades with P&L
SELECT t.id, t.entry_price, t.exit_price, t.pnl, t.result FROM trades t;

# Daily summary
SELECT 
    a.date,
    COUNT(DISTINCT a.id) as alerts,
    COUNT(DISTINCT t.id) as trades,
    SUM(t.pnl) as total_pnl
FROM alerts a
LEFT JOIN trades t ON a.id = t.alert_id
GROUP BY a.date
ORDER BY a.date DESC;
```

---

## Summary

| Aspect | Details |
|--------|---------|
| **Storage** | SQLite database (`src/trading/trades.db`) |
| **Workflow** | Alert → Fill → Report |
| **Tables** | alerts, trades, daily_stats |
| **P&L Calc** | `(exit - entry) × 20` for MNQ |
| **Status** | PENDING → FILLED |
| **Access** | TradeJournal class or CLI tool |
| **Backup** | Copy trades.db file |
