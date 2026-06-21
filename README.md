# MNQ Trading Agent v3 — VWAP/POC System

**Current Version:** 3.0  
**System:** VWAP Bounce Detection + MA Confirmation  
**Status:** Production Ready  
**Last Updated:** 2026-06-20

---

## Overview

A fully automated MNQ trading alert system that:

1. **Detects 5m VWAP bounces** — Primary entry signal
2. **Confirms with 15m MA alignment** — Avoids false signals
3. **Filters with Claude AI** — Probability assessment
4. **Tracks exits automatically** — Records TP/SL hits
5. **Sends Discord alerts** — Real-time notifications

**Target Performance:**
- 2-5 alerts per trading day
- 55-60% win rate
- 6-10 confluence score for alert generation

---

## Quick Start (60 seconds)

### 1. Verify Configuration

```bash
cat .env
```

Must have: `PROJECTX_USERNAME`, `PROJECTX_API_KEY`, `ANTHROPIC_API_KEY`, `DISCORD_WEBHOOK_URL`, `FINNHUB_API_KEY`

### 2. Start Agent (Terminal 1)

```bash
python src/core/run.py
```

### 3. Start Monitor (Terminal 2)

```bash
python src/monitoring/monitor.py
```

Done! System is monitoring for VWAP bounces and tracking exits.

---

## Key Files

### Core System
- **`src/core/agent.py`** — Main trading agent (VWAP/POC v3)
- **`src/core/run.py`** — Entry point
- **`src/monitoring/monitor.py`** — Exit tracking daemon

### Analysis
- **`src/analysis/vwap_analyzer.py`** — VWAP bounce detection
- **`src/analysis/ma_analyzer.py`** — MA alignment checking
- **`src/analysis/volume_analyzer.py`** — Volume & POC analysis
- **`src/analysis/probability_engine.py`** — Claude AI filtering

### Configuration
- **`src/data/config.py`** — All settings (thresholds, timeframes, MA periods)
- **`src/data/data_fetcher.py`** — ProjectX API connection
- **`.env`** — Secrets (credentials, API keys, webhooks)

### Database & Views
- **`src/database/alert_db.py`** — Alert storage
- **`src/database/trade_db.py`** — Trade exit tracking
- **`src/views/discord_view.py`** — Discord integration

---

## Entry Logic (Simple)

### VWAP Bounce (5m)

```
1. Price touches/crosses VWAP
2. Current bar forms reversal (close opposite of open)
3. Body size > 50% of range
4. Bounce detected → proceed
```

### MA Confirmation (15m)

```
Bullish Entry:  MA5 > MA20 > MA50
Bearish Entry:  MA5 < MA20 < MA50
No alignment:   Alert skipped
```

### Confluence Score (0-10)

```
VWAP bounce:      +3 pts (always)
15m MA aligned:   +2 pts (always)
Volume spike:     +0-2 pts (depends on volume)
POC proximity:    +1 pt (if within 5 pts)
MA5 proximity:    +1 pt (if within 5 pts)
─────────────────────────
Total needed:     ≥6 pts to alert
```

### Claude Filter

```
All alerts → sent to Claude
Claude says "skip" → alert filtered out
Claude says "alert" → Discord sent + database saved
```

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│ ProjectX/TopstepX API                                  │
│ (MNQ contract data: 5m, 15m, 1d bars)                  │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                 │
┌───────▼──────────────┐       ┌──────────▼─────────┐
│ Agent (run.py)       │       │ Monitor (monitor.py)│
│ Generates Alerts     │       │ Tracks Exits        │
│ • VWAP bounce detect │       │ • Polls MNQ price   │
│ • MA confirmation    │       │ • Checks SL/TP      │
│ • Claude filtering   │       │ • Records trades    │
│ • Confluence score   │       │                     │
└───────┬──────────────┘       └──────────┬──────────┘
        │                                 │
        └────────────────┬────────────────┘
                         │
              ┌──────────▼──────────┐
              │ Alert Database      │
              │ • Pending alerts    │
              │ • Recorded trades   │
              │ • Performance stats │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │ Discord Webhook     │
              │ • Alert messages    │
              │ • Exit notifications│
              └─────────────────────┘
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| **QUICK_START.md** | 60-second setup & common issues |
| **VWAP_POC_SYSTEM_SPEC.md** | Complete technical specification |
| **docs/ALERT_MANAGEMENT_GUIDE.md** | Managing alerts in database |
| **docs/TRADE_JOURNAL_GUIDE.md** | Trade tracking & journal |
| **docs/AUTO_TP_SL_MONITORING.md** | Exit tracking details |
| **docs/EXIT_TYPE_TRACKING.md** | Exit types & status codes |
| **MVC_STRUCTURE.md** | Code architecture (MVC pattern) |

---

## Configuration Adjustments

**Location:** `src/data/config.py`

### Lower Alert Rate (More Selective)
```python
CONFLUENCE_THRESHOLD = 7        # Increase from 6
VOLUME_SPIKE_MULTIPLIER = 1.5   # Increase from 1.2
```

### Higher Alert Rate (More Signals)
```python
CONFLUENCE_THRESHOLD = 5        # Decrease from 6
VOLUME_SPIKE_MULTIPLIER = 1.0   # Decrease from 1.2
```

### Adjust Timeframes
```python
TIMEFRAMES = {
    "1d":  {"elementSize": 1440, "maxlen": 250},
    "15m": {"elementSize": 15,   "maxlen": 2000},
    "5m":  {"elementSize": 5,    "maxlen": 3000},
}
```

After any config change: **restart agent** with `python src/core/run.py`

---

## Database Queries

### View Recent Alerts

```bash
sqlite3 trades.db "SELECT timestamp, direction, current_price, confluence_score, assessment FROM alerts ORDER BY timestamp DESC LIMIT 10;"
```

### View Trade Performance

```bash
sqlite3 trades.db "SELECT direction, COUNT(*) as total, SUM(CASE WHEN result='TP_HIT' THEN 1 ELSE 0 END) as wins, ROUND(SUM(CASE WHEN result='TP_HIT' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate FROM trades GROUP BY direction;"
```

### Average Confluence Score

```bash
sqlite3 trades.db "SELECT ROUND(AVG(confluence_score), 1) as avg_score FROM alerts;"
```

---

## Troubleshooting

### Agent Won't Connect
- ✅ Verify ProjectX credentials in `.env`
- ✅ Check network connectivity
- ✅ Ensure MNQ contract is available

### No Alerts After 1+ Hour
- ✅ Check logs: "VWAP bounce detected"
- ✅ Verify 15m MAs are calculating
- ✅ Increase `CONFLUENCE_THRESHOLD` lower
- ✅ Check Claude API quota

### High False Alert Rate
- ✅ Increase `CONFLUENCE_THRESHOLD` (6 → 7)
- ✅ Increase `VOLUME_SPIKE_MULTIPLIER` (1.2 → 1.5)
- ✅ Check Claude assessment (may be too permissive)

### Discord Messages Not Sending
- ✅ Verify webhook URL in `.env`
- ✅ Test webhook manually
- ✅ Run monitor with `--discord-off` to disable

---

## Performance Monitoring

### Daily Metrics

```bash
# Count alerts today
sqlite3 trades.db "SELECT COUNT(*) FROM alerts WHERE DATE(timestamp) = DATE('now');"

# Win rate today
sqlite3 trades.db "SELECT ROUND(SUM(CASE WHEN result='TP_HIT' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate FROM trades WHERE DATE(timestamp) = DATE('now');"

# Average confluence today
sqlite3 trades.db "SELECT ROUND(AVG(confluence_score), 1) FROM alerts WHERE DATE(timestamp) = DATE('now');"
```

---

## Support & Debugging

### Enable Verbose Logging

```bash
# Edit src/core/agent.py
# Change: logging.basicConfig(level=logging.INFO, ...)
# To:     logging.basicConfig(level=logging.DEBUG, ...)

python src/core/run.py > debug.log 2>&1
tail -f debug.log
```

### Check System Health

```bash
# Verify all modules load
python -c "
from src.core.agent import main
from src.monitoring.monitor import *
from src.analysis.vwap_analyzer import *
from src.analysis.ma_analyzer import *
print('All imports OK')
"
```

---

## Version History

- **v3.0** (Current) — VWAP/POC system with MA confirmation
  - Primary: 5m VWAP bounce
  - Confirmation: 15m MA alignment
  - Filter: Claude probability
  - Exit: Auto TP/SL tracking

- **v2.x** — Sweep detection system (deprecated)
  - Used multi-timeframe sweep alignment
  - Required 3+ TF alignment (too restrictive)
  - Generated 0 alerts in 3 sessions

- **v1.x** — Initial prototype (deprecated)

---

## Next Steps

1. **Run live for 3+ sessions** — Collect performance data
2. **Monitor win rate** — Target 55-60%
3. **Adjust thresholds** — Based on results
4. **Fine-tune Claude prompt** — If filtering too much
5. **Deploy to production** — Once validated

---

## Contacts & Support

- **Agent Issues:** Check `QUICK_START.md` troubleshooting
- **Config Questions:** See `VWAP_POC_SYSTEM_SPEC.md` section 9
- **Database Queries:** See `docs/TRADE_JOURNAL_GUIDE.md`
- **Discord Integration:** See `docs/ALERT_MANAGEMENT_GUIDE.md`

---

**Status:** Production Ready  
**Last Validated:** 2026-06-20  
**Next Review:** After 3 live sessions
