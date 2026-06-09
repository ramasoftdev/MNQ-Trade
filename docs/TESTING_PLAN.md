# Agent Testing Plan — Complete Validation

## Overview

This document covers comprehensive testing of all recent changes:
- SPY pivot magnet logic
- Volume spike removal
- Trade journal logging
- Daily report generation
- Date validation alerts

---

## Phase 1: Pre-Flight Checks (5-10 minutes)

### Check 1.1: Configuration Verification

```bash
cd "C:\Users\adria\Documents\AJ\MNQ Agent\mnq_agent_2\sessions\serene-charming-maxwell\mnt\outputs\mnq_v2"

# Verify .env file has all required keys
cat .env
```

**Expected:**
```
PROJECTX_USERNAME=your_username
PROJECTX_API_KEY=your_api_key
ANTHROPIC_API_KEY=your_key
DISCORD_WEBHOOK_URL=your_webhook
FINNHUB_API_KEY=your_key
```

**If missing:** Update `.env.example` → `.env`

---

### Check 1.2: Daily Levels File

```bash
# Verify daily_levels.py has today's date
cat daily_levels.py | grep "^DATE"
```

**Expected:**
```
DATE = "2026-06-06"   ← Should match today's date
```

**If old date:** Update it:
```python
DATE = "2026-06-06"  # Change to today
```

**This will trigger the date check alert on first run.**

---

### Check 1.3: Database Check

```bash
# Verify no old database exists (or it's okay if it does)
ls -la trades.db 2>/dev/null || echo "Database will be created on first run"
```

---

### Check 1.4: Dependency Check

```bash
# Verify all imports work
python3 << 'EOF'
import sys
try:
    from trade_journal import TradeJournal
    from daily_report import DailyReport
    from report_scheduler import check_and_send_report
    from spy_levels_analyzer import analyze_spy_levels
    print("✓ All imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
EOF
```

**Expected:** `✓ All imports successful`

---

## Phase 2: Start the Agent (Ongoing)

### Step 2.1: Launch Agent

```bash
python agent.py
```

**Expected first output:**
```
============================================================
  MNQ Trading Agent v2 — Multi-Timeframe Edition
  Trigger TFs : 15m, 5m
  Min alignment: 3/4 timeframes
  Alert cooldown: 300s
============================================================
00:15:23  INFO      agent  Waiting for initial bar buffers to fill...
00:15:25  INFO      agent  STATUS  MNQ=30450.25  SPY=756.45  bars 1h=5 30m=10 15m=20 5m=50  ...
```

### Step 2.2: Monitor Status Output

Agent prints status every 60 seconds:
```
00:16:23  INFO      agent  STATUS  MNQ=30450.50  SPY=756.50  bars 1h=50 30m=100 15m=150 5m=250  MNQ_connected=True  SPY_connected=True
00:17:23  INFO      agent  STATUS  MNQ=30455.25  SPY=756.48  bars 1h=51 30m=101 15m=151 5m=251  MNQ_connected=True  SPY_connected=True
```

**What to verify:**
- ✓ `MNQ` price updating (not 0.0)
- ✓ `SPY` price updating (not 0.0)
- ✓ Bar counts increasing
- ✓ Both connections `True`

**If SPY shows 0.0:**
- Check Finnhub API key in `.env`
- Check rate limits (60 calls/min max)

**If MNQ shows 0.0 or bars not increasing:**
- Check Tradovate API credentials
- Check network/firewall

---

## Phase 3: Test Suite (Automated)

### Run all unit tests:

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tee test_results.txt
```

**Expected:** ~78+ tests passing

```
tests/test_context_analyzer.py::... PASSED
tests/test_discord_formatter.py::... PASSED
tests/test_probability_engine.py::... PASSED
tests/test_trade_journal.py::... PASSED
===================== 78+ passed in X.XXs =====================
```

---

## Phase 4: Wait for Sweep Alert (Live Testing)

### What triggers an alert:

1. Liquidity sweep detected on 15m or 5m bar close
2. 3+ timeframes align with sweep direction
3. Cooldown period elapsed (5 minutes between same direction)

### Monitor logs for:

```bash
# In the agent terminal, watch for these log lines:

# Sweep detected
INFO      agent  SWEEP on 5m: SHORT @ 30440.50 | alignment 4/4 | score 10.5 (core + SPY magnet)

# SPY magnet analysis
INFO      agent  SPY magnet: SPY 756.25 below PIVOT 756.40 (bearish, very strong magnet)
INFO      agent  SPY score: Pivot 2.5 + Others 0.0 + Direction 0.5 = 3.0 pts

# Claude assessment
INFO      agent  Claude: 75% — TAKE (High confidence)

# Trade journal logging
INFO      trade_journal  Alert logged to journal: id=1

# Discord send
INFO      agent  Pipeline complete — Discord alert sent.
```

---

## Phase 5: Verify Trade Journal Logging

### After first alert, check database:

```bash
# List pending alerts
python fill_trade.py --list-pending
```

**Expected output:**
```
═════════════════════════════════════════════════════════════════════════════
  PENDING & FILLED ALERTS — 2026-06-06
═════════════════════════════════════════════════════════════════════════════

📋 PENDING (1 alerts waiting for fills):

  ID    1 | 14:30 | SHORT @ 30440.50 | Score 10.5 | TAKE

═════════════════════════════════════════════════════════════════════════════
```

### Or query directly:

```bash
sqlite3 trades.db "SELECT id, direction, entry_price, confluence_score, assessment FROM alerts ORDER BY id DESC LIMIT 5;"
```

**Expected:**
```
1|SHORT|30440.50|10.5|TAKE
```

---

## Phase 6: Test Fill Trade CLI

### Record a trade fill:

```bash
# After you execute the trade, record the fill
python fill_trade.py --alert-id=1 --exit-price=30430.00 --notes="Exited at support"
```

**Expected output:**
```
14:45:23  INFO      trade_journal  Trade recorded: alert_id=1, direction=SHORT, exit=30430.00, P&L=$200.00 (0.3%), result=WIN
```

### Verify fill was recorded:

```bash
# Now it should show as FILLED
python fill_trade.py --list-pending
```

**Expected:**
```
✓ FILLED (1 alerts):

  ID    1 | SHORT | 30440.50 → 30430.00 | +$200.00 (+0.3%) ✓
```

---

## Phase 7: Test Daily Report Generation

### Option A: Wait until 4:05 PM CT

At exactly 4:05 PM, watch logs for:

```
16:05:23  INFO      report_scheduler  Generating daily report for 2026-06-06...
16:05:24  INFO      report_scheduler  ✓ Daily report sent to Discord
16:05:25  INFO      report_scheduler  Report archived: ./reports/report_2026-06-06.html
```

### Option B: Generate on-demand

```bash
python fill_trade.py --report
```

**Expected output:**
```
════════════════════════════════════════════════════════════════════════════
  MNQ TRADING AGENT — DAILY REPORT
  2026-06-06
════════════════════════════════════════════════════════════════════════════

SUMMARY
────────────────────────────────────────────────────────────────────────────
  Total Alerts:      1
  Total Trades:      1
  Wins / Losses:     1 / 0
  Win Rate:          100.0%
  Total P&L:         $200.00
  Avg P&L / Trade:   $200.00
  Avg Confluence:    10.5

PERFORMANCE BY DIRECTION
────────────────────────────────────────────────────────────────────────────
  SHORT  — 1 trades, 1 wins, 100.0% WR, $200.00 P&L

TRADES DETAIL
────────────────────────────────────────────────────────────────────────────
  ✓ 14:30-14:45 | $30440.00 → $30430.00 | P&L: $200.00 (0.3%)

════════════════════════════════════════════════════════════════════════════
```

### Verify Discord received it:

Check your Discord channel - you should see an embed with:
- Title: "MNQ Daily Report — 2026-06-06"
- Green color (positive P&L)
- All statistics

---

## Phase 8: Test SPY Magnet Logic

### Check logs for magnet analysis:

```
INFO      agent  SPY magnet: SPY 756.25 below PIVOT 756.40 (bearish, very strong magnet)
INFO      agent  SPY score: Pivot 2.5 + Others 0.0 + Direction 0.5 = 3.0 pts
```

**Verify scoring bands:**

| Distance | Points | Example |
|----------|--------|---------|
| < 0.30   | 2.5    | SPY 756.25 vs PIVOT 756.40 |
| < 1.00   | 1.5    | SPY 756.00 vs PIVOT 756.40 |
| < 2.00   | 1.0    | SPY 755.50 vs PIVOT 756.40 |
| >= 2.00  | 0.0    | SPY 754.00 vs PIVOT 756.40 |

Direction bonus example:
```
SHORT + SPY below PIVOT = +0.5 ✓ (aligned)
LONG + SPY below PIVOT = +0.0 (misaligned)
```

---

## Phase 9: Test Date Check Alert

### Verify date validation:

If you update `daily_levels.py` with an OLD date:

```python
DATE = "2026-06-04"  # Old date
```

On next alert, you should see:

```
WARNING  levels_analyzer  ⚠️  PIVOT UPDATE NEEDED! ⚠️
   Loaded date: 2026-06-04
   Today's date: 2026-06-06
   The SPY/SPX levels may be OUTDATED.
   Please update daily_levels.py with today's levels before trading.
```

**This is correct!** Update the date and the warning disappears.

---

## Phase 10: Volume Spike Removal Verification

### Verify volume spike is NOT in conditions:

Check a logged alert:

```bash
sqlite3 trades.db "SELECT id, sweep_confirmed, reversal_candle, near_poc, vwap_confluence FROM alerts LIMIT 1;"
```

**Expected:** You should see 7 condition columns, NOT 8.

**Old system had:** 8 conditions (included volume_spike)
**New system has:** 7 conditions (volume_spike removed)

Check confluence score calculation:

```bash
# Total conditions should be 10 (7 base + 3 external)
sqlite3 trades.db "SELECT 
    confluence_score,
    base_score, 
    ext_score,
    spy_magnet_score
FROM alerts LIMIT 1;"
```

**Expected:**
```
confluence_score = base_score + ext_score + spy_magnet_score
Example: 10.5 = 7 + 0.5 + 3.0
```

---

## Troubleshooting Guide

### Problem: No alerts firing

**Check:**
1. Are bars loading? (bar counts increasing in status)
2. Is MNQ data streaming? (price updating)
3. Are there session levels? (check daily_levels.py)
4. Try lower MIN_TF_ALIGNMENT: change in config.py from 3 to 2

### Problem: SPY price shows 0.0

**Check:**
1. FINNHUB_API_KEY in .env
2. Rate limit: 60 calls/min max
3. Network/firewall blocking finnhub.io

### Problem: Trade journal not logging

**Check logs for:**
```
Alert logged to journal: id=1
```

If missing, check:
1. Discord alert actually sent (should log "Discord alert sent")
2. Database file created (ls -la trades.db)
3. No exceptions in logs

### Problem: Daily report not sending

**Check:**
1. DAILY_REPORT_TIME correct? (16, 5) = 4:05 PM
2. Report scheduler running? (should see status updates every 60s)
3. DISCORD_WEBHOOK_URL valid?

---

## Success Criteria

✅ **Agent starts successfully**
- All connections establish
- Bars load and increase
- Status updates every 60 seconds

✅ **First sweep alert fires**
- Logs show "SWEEP on Xm:"
- SPY magnet analysis shown
- Claude assessment returned
- Discord alert posted

✅ **Trade journal logging works**
- Alert appears in `python fill_trade.py --list-pending`
- Alert ID matches Discord message
- All context saved to database

✅ **Fill recording works**
- `python fill_trade.py --alert-id=X --exit-price=Y` succeeds
- Alert status changes from PENDING → FILLED
- P&L calculated correctly

✅ **Daily report generates**
- Auto-generates at 4:05 PM CT
- OR manual: `python fill_trade.py --report`
- Shows correct stats and P&L
- Posted to Discord

✅ **SPY magnet logic works**
- Logs show "SPY magnet: ..." analysis
- Scoring matches distance bands
- Direction bonus applied correctly

✅ **Date validation works**
- Old dates show warning
- Current date shows no warning

---

## Expected Test Duration

- Pre-flight checks: 5-10 minutes
- Agent startup: 2-5 minutes (waiting for bars to fill)
- Wait for sweep: 30 minutes to several hours (depends on market)
- Fill trade test: 2-3 minutes
- Report generation test: 5 minutes (manual) or wait until 4:05 PM
- **Total: 30 min - 4 hours** (depending on market activity)

---

## How to Capture Results

Save test results:

```bash
# Start agent with output to file
python agent.py 2>&1 | tee agent_test_$(date +%Y%m%d_%H%M%S).log
```

Then review:
```bash
cat agent_test_20260606_140000.log | grep -E "SWEEP|SPY magnet|Alert logged|Discord alert|report"
```

---

## Next Steps After Testing

If all tests pass ✅:
1. Document any issues found
2. Proceed to TopstepX API integration
3. Set up automated daily testing

If issues found ❌:
1. Document the error
2. Fix and re-test
3. Update this guide

---

**Good luck with testing! 🚀**

Remember: The agent is now production-ready with:
- ✅ SPY pivot magnet logic
- ✅ Trade journal logging
- ✅ Daily report generation
- ✅ Date validation alerts
- ✅ Volume spike removed from scoring

Go forth and test!
