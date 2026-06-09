# Automatic TP/SL Monitoring — Real-Time Alerts

## Overview

The system now **automatically monitors ALL alerts** (taken or skipped) and sends **instant Discord notifications** when TP or SL is hit.

```
Alert detected @ 10:30
   ↓ (system starts monitoring)
Price touches TP @ 2:00 PM
   ↓ (automatic detection)
Discord alert sent instantly
   ↓ (automatic fill recorded)
Exit type stored: "TP_HIT"
```

---

## What's Automatic Now

✅ **Monitor ALL alerts** — Both taken and skipped  
✅ **Detect TP/SL hits** — Compare current price to thresholds  
✅ **Send Discord alerts** — Instant notification with details  
✅ **Record exit automatically** — Fill recorded, exit type stored  
✅ **Run continuously** — Background thread checks every 5 seconds  

---

## How It Works

### Background Monitoring Loop

When the agent starts, it launches a background thread that:

1. **Every 5 seconds:**
   - Gets current MNQ price
   - Fetches all open alerts (those with SL/TP set)
   - Checks if price touched any SL or TP

2. **When TP/SL is touched:**
   - Auto-records the fill in database
   - Marks alert as notified (prevents duplicate alerts)
   - Sends Discord alert with details
   - Stores exit_type: "TP_HIT" or "SL_HIT"

3. **Continuous:**
   - Runs in background until agent stops
   - No manual intervention needed
   - Tracks ALL alerts regardless of taken status

---

## Discord Notifications

### When TP is Hit

```
📍 Alert #42 — TP_HIT
Status: ✓ TAKEN
Direction: LONG
Entry: 30450.50 | Current: 30498.00
SL: 30426.75 | TP: 30498.00
Confidence: 9.5
```

### When SL is Hit

```
⛔ Alert #43 — SL_HIT
Status: ✗ SKIPPED
Direction: SHORT
Entry: 30475.25 | Current: 30430.00
SL: 30490.50 | TP: 30450.00
Confidence: 6.2
```

### What Info Is Sent

- ✅ Alert ID
- ✅ Hit type (TP_HIT or SL_HIT)
- ✅ Taken status (did you take it or skip it?)
- ✅ Direction (LONG or SHORT)
- ✅ Entry, Current, SL, TP prices
- ✅ Confidence score
- ✅ Timestamp

---

## Example Workflow

### Day: All Alerts Monitored

```
10:30 AM — Alert #42 detected (LONG @ 30450.50, Score 9.5)
           System: Auto-calculates SL: 30426.75, TP: 30498.00
           System: Starts monitoring in background

10:35 AM — You review alert, decide to TAKE it
           $ python -m src.trading.fill_trade --alert-id=42 --take
           System: Confirms SL/TP are set, continues monitoring

10:45 AM — Alert #43 detected (SHORT @ 30475.25, Score 6.2)
           System: Auto-calculates SL: 30490.50, TP: 30450.00
           System: Starts monitoring (you skip this one)

2:00 PM  — Price touches 30498.00 (Alert #42's TP)
           System: Detects hit!
           System: Auto-records fill at 30498.00
           System: Sends Discord: "📍 Alert #42 — TP_HIT ✓ TAKEN"
           Database: exit_type = "TP_HIT"

2:30 PM  — Price touches 30450.00 (Alert #43's TP)
           System: Detects hit! (even though you skipped it)
           System: Auto-records fill at 30450.00
           System: Sends Discord: "📍 Alert #43 — TP_HIT ✗ SKIPPED"
           Database: exit_type = "TP_HIT" (for a skipped alert)

EOD      — You check results:
           $ python -m src.trading.fill_trade --list-pending
           Shows: Alert #42 filled with TP_HIT (you took it, won)
           Shows: Alert #43 filled with TP_HIT (you skipped it, would have won)
           
           This shows you: "I skipped an alert that would have won!"

Friday   — Weekly analysis:
           $ python -m src.trading.fill_trade --exit-analysis
           Shows: Score 6.2 alerts hit TP 50% of the time
           Shows: You skipped a 6.2 alert and it hit TP
```

---

## Database Columns (New)

### In `alerts` table:

| Column | Type | Purpose |
|--------|------|---------|
| `tp_sl_notified` | BOOLEAN | Have we sent the notification? (prevents duplicates) |
| `tp_sl_hit_at` | DATETIME | When SL/TP was hit |

### In `trades` table:

Auto-filled fields when TP/SL hit:
- `exit_price` — Price where TP/SL was touched
- `exit_type` — "TP_HIT" or "SL_HIT" (auto-detected)
- `pnl` — Auto-calculated
- `result` — "WIN", "LOSS", or "BREAK_EVEN"

---

## Key Behaviors

### 1. Monitors ALL Alerts
```
Alert status: DOESN'T MATTER
- Taken alerts → monitored ✓
- Skipped alerts → monitored ✓
- All alerts monitored regardless
```

### 2. Prevents Duplicate Alerts
```
TP hit at 30498.00
  → sends one Discord alert
  → sets tp_sl_notified = 1
  → won't send again if price touches TP again
```

### 3. Auto-Records Fills
```
When SL/TP hit:
  → Automatically creates entry in trades table
  → Calculates P&L
  → Stores exit_type
  → Updates alert status to FILLED
  → No manual recording needed!
```

### 4. Runs Continuously
```
Agent starts
  → TP/SL monitor thread launches
  → Checks every 5 seconds
  → Runs until agent stops
  → Survives reboots if alert still pending
```

---

## Technical Details

### Monitoring Loop

```python
# In agent.py
def tp_sl_monitor_loop():
    while True:
        time.sleep(5)  # Check every 5 seconds
        
        # Get current price
        current_price = fetcher.get_latest_price()
        
        # Get all open alerts (with SL/TP, not yet notified)
        open_alerts = journal.get_open_alerts_for_monitoring()
        
        for alert in open_alerts:
            # Check if price hit SL or TP
            hit_type, hit_price = journal.check_and_record_tp_sl_hit(alert_id, current_price)
            
            if hit_type:
                # Auto-record fill
                # Send Discord alert
                send_tp_sl_alert(...)
```

### Price Tolerance

- **Tolerance:** 0.1 points
- **Reason:** Account for tick size and market volatility
- Example: If TP is 30498.00, touching 30497.95 counts as hit

### Check Interval

- **Every 5 seconds**
- **Why 5s:** Balance between responsiveness and CPU usage
- **Can adjust:** Change `time.sleep(5)` in tp_sl_monitor_loop()

---

## Seeing It In Action

### View Alerts with Auto-Recorded Fills

```bash
python -m src.trading.fill_trade --list-pending
```

**Output will show:**
```
✓ FILLED (2 trades):
  ID   42 | LONG  | 30450.50 → 30498.00 | +$950 ✓ 📍 TP_HIT
  ID   43 | SHORT | 30475.25 → 30450.00 | +$500 ✓ 📍 TP_HIT
```

Note: These auto-recorded fills will show even if you didn't manually use `--exit-price`!

### Check Discord Notifications

Watch your Discord channel when:
- You take an alert (system monitoring it)
- Price moves toward your SL/TP
- Price touches it
- Discord alert appears instantly

### Analyze Including Skipped Alerts

```bash
python -m src.trading.fill_trade --exit-analysis
```

**Output shows:**
```
Band       Total    TP Hit    SL Hit    TP Rate
──────────────────────────────────────────────
10+            7         5         0      71%
8-10           6         3         2      50%  ← Mixed results
5-8            4         0         4       0%  ← All hit SL
```

Notice: Score 5-8 shows alerts that you may have skipped, but they all hit SL. This proves those low-score alerts don't work!

---

## Benefits

✅ **No Manual Recording** — Auto-detected and recorded  
✅ **Real-Time Alerts** — Instant Discord notifications  
✅ **Complete Tracking** — Even skipped alerts tracked  
✅ **Decision Insights** — See what would have happened  
✅ **Zero Latency** — Notifications sent as soon as hit occurs  
✅ **Continuous Monitoring** — Runs 24/5 in background  

---

## Edge Cases

### What if price gaps through SL/TP?

The system checks if current price is `>=` TP (or `<=` SL).

**Example:**
- TP: 30498.00
- Price gaps from 30496 to 30500
- **Result:** TP_HIT detected (price is now past TP)

### What if price hovers around SL/TP?

The system sends ONE notification and sets `tp_sl_notified = 1`.

**Example:**
- TP: 30498.00
- Price: 30498.05 (within tolerance)
- **Result:** One notification sent, won't repeat even if it bounces

### What if you manually record exit after auto-record?

The trade already exists (auto-recorded), so:
- Manual record will fail (alert_id already has a trade)
- Or it will update the existing record

**Best practice:** Don't manually record exits that were auto-detected. Just check the alerts!

---

## Configuration

### Check Interval

Default: 5 seconds

To change, edit `agent.py`:
```python
def tp_sl_monitor_loop():
    while True:
        time.sleep(5)  # Change this number
```

**Options:**
- `1`: Very responsive, but higher CPU
- `5`: Balanced (recommended)
- `10`: Light, but slower detection

### Price Tolerance

Default: 0.1 points

To change, edit `trade_journal.py`:
```python
def check_and_record_tp_sl_hit(...):
    tolerance = 0.1  # Change this number
```

---

## Workflow Summary

### Before (Manual)
```
1. Alert detected
2. You manually review
3. You manually record exit
4. You manually check database
5. You manually analyze
```

### After (Automatic)
```
1. Alert detected & auto-monitored ✓
2. You get instant Discord alert ✓
3. Exit auto-recorded ✓
4. Database auto-updated ✓
5. You run analysis command ✓
```

---

## Key Insight

You now have **complete visibility** into:
- ✓ Alerts you took (and how they performed)
- ✓ Alerts you skipped (and what would have happened)
- ✓ When each hit TP or SL
- ✓ Why you should keep/skip certain confidence scores

This automatic monitoring transforms your journal from a **record** into an **analysis tool**.

---

## Next Steps

1. **Start the agent:** `python src/core/run.py`
2. **Monitor Discord:** Watch for TP/SL hits
3. **Review alerts:** `python -m src.trading.fill_trade --list-pending`
4. **Analyze weekly:** `python -m src.trading.fill_trade --exit-analysis`
5. **Adjust:** Trade only scores that hit TP

That's it! Everything else is automatic. 🎯
