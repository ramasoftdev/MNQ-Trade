# MNQ Agent v3 — Quick Start Guide

## Prerequisites

```bash
# 1. Verify .env is configured
cat .env
# Should contain:
# PROJECTX_USERNAME=your_username
# PROJECTX_API_KEY=your_api_key
# ANTHROPIC_API_KEY=your_claude_key
# DISCORD_WEBHOOK_URL=your_webhook
# FINNHUB_API_KEY=your_finnhub_key
```

---

## Start the System

### Terminal 1 — Agent (Alert Generation)

```bash
python src/core/run.py
```

**Expected output:**
```
======================================================================
  MNQ Trading Agent v3 — VWAP/POC System
  Entry: 5m VWAP bounce + 15m MA confirmation
  Confluence threshold: 6/10 pts
======================================================================

Waiting for initial bar buffers to fill...
All timeframe buffers ready. Monitoring for VWAP bounces...

STATUS  MNQ=19550.00  SPY=562.50  bars 1d=250 15m=2000 5m=3000  
MNQ_connected=True  SPY_connected=True
```

### Terminal 2 — Monitor (Exit Tracking)

```bash
# With Discord notifications
python src/monitoring/monitor.py

# Or without Discord (testing)
python src/monitoring/monitor.py --discord-off
```

**Expected output:**
```
[INFO] monitor — Starting MNQ price monitor
[INFO] monitor — Market hours: 8:30 AM - 4:00 PM CT
[INFO] monitor — Polling for pending alert exits...
```

---

## What to Expect

### When Alert Fires:

**Terminal 1 (Agent):**
```
05:42:15  INFO  VWAP bounce detected: LONG
05:42:15  INFO  15m MAs confirmed bullish for LONG
05:42:15  INFO  Confluence Score: 8/10 pts
05:42:15  INFO  Claude: 72% probability | Confidence: HIGH
05:42:15  INFO  Alert saved: ID=12345
05:42:15  INFO  Discord notification sent
```

**Discord Message:**
```
[ALERT] LONG Entry
MNQ: $19,550.00
SL: $19,535.00 | TP: $19,570.00
Confluence: 8/10 | Claude: 72% probability
Time: 05:42 CT
```

### When Exit Hits:

**Terminal 2 (Monitor):**
```
05:45:30  INFO  TP HIT on alert #12345 (LONG)
05:45:30  INFO  Exit recorded: $19,570.00 (+$20.00)
05:45:30  INFO  Discord notification sent
```

**Discord Message:**
```
[EXIT] LONG Trade #12345
Result: TP HIT ✓
Entry: $19,550.00
Exit: $19,570.00
P&L: +$100.00 (+$20 per point × 5 multiplier)
Time: 05:45 CT
```

---

## System Status Checks

### Check Agent is Running

```bash
# In Terminal 1, you should see status every 60 seconds:
STATUS  MNQ=19550.00  SPY=562.50  bars 1d=250 15m=2000 5m=3000  
MNQ_connected=True  SPY_connected=True
```

### Check Monitor is Running

```bash
# In Terminal 2, monitor should be polling:
[INFO] Polling current price: $19,550.00
[INFO] 2 pending alerts
```

### Check Database

```bash
# View saved alerts
sqlite3 trades.db "SELECT id, direction, current_price, confluence_score FROM alerts ORDER BY timestamp DESC LIMIT 5;"

# View recorded trades
sqlite3 trades.db "SELECT id, alert_id, entry_price, exit_price, result FROM trades ORDER BY timestamp DESC LIMIT 5;"
```

---

## Troubleshooting

### Agent Won't Start

```bash
# Check imports
python -c "from src.core.agent import main; print('OK')"

# Check ProjectX credentials
python -c "from src.data.config import PROJECTX_USERNAME; print(PROJECTX_USERNAME)"
```

### No Alerts Generated

1. Check confluence threshold: `grep CONFLUENCE_THRESHOLD src/data/config.py`
2. Check if 5m bars are closing: look for "5m bar closed" in logs
3. Check if 15m MAs are aligned: insufficient bars or not aligned
4. Verify volume spike threshold: `grep VOLUME_SPIKE_MULTIPLIER src/data/config.py`

### Monitor Shows 0 Pending Alerts

1. Agent may not have generated alerts yet
2. Alerts may have already exited
3. Check database: `sqlite3 trades.db "SELECT COUNT(*) FROM alerts;"`

### Discord Not Sending

1. Verify webhook URL: `grep DISCORD_WEBHOOK_URL .env`
2. Test webhook: `curl -X POST [WEBHOOK_URL] -H 'Content-Type: application/json' -d '{"content":"Test"}'`
3. Disable Discord during testing: `python src/monitoring/monitor.py --discord-off`

---

## Configuration

**Main config file:** `src/data/config.py`

**Key settings:**
```python
CONFLUENCE_THRESHOLD = 6         # Min score for alert
ALERT_COOLDOWN_SECS = 300        # 5 min cooldown per direction
VOLUME_SPIKE_MULTIPLIER = 1.2    # Volume spike threshold
```

**To adjust:**
1. Edit `src/data/config.py`
2. Restart agent: `python src/core/run.py`

---

## Performance Targets

| Metric | Target | How to Monitor |
|--------|--------|---|
| Alerts/day | 2-5 | `sqlite3 trades.db "SELECT COUNT(*) FROM alerts WHERE DATE(timestamp) = DATE('now');"`  |
| Win rate | 55-60% | Count TP_HIT vs SL_HIT in trades table |
| Avg confluence | 7.0 | `sqlite3 trades.db "SELECT AVG(confluence_score) FROM alerts;"`  |

---

## Log Files

Logs are printed to console but you can redirect:

```bash
# Save to file
python src/core/run.py > agent.log 2>&1 &

# Watch live
tail -f agent.log

# Search for errors
grep -i error agent.log
```

---

## Stop the System

```bash
# Terminal 1 (Agent)
Ctrl+C

# Terminal 2 (Monitor)
Ctrl+C
```

Unsaved trades remain in database and will be tracked next session.

---

## Full Documentation

For detailed information, see:
- `VWAP_POC_SYSTEM_SPEC.md` — Complete system specification
- `docs/ALERT_MANAGEMENT_GUIDE.md` — Alert management
- `docs/TRADE_JOURNAL_GUIDE.md` — Trade tracking
- `docs/AUTO_TP_SL_MONITORING.md` — Exit tracking

---

**Version:** 3.0 — VWAP/POC System  
**Status:** Production Ready
