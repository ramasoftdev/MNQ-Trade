# MNQ Trading Agent v2 — Complete Documentation

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Features](#core-features)
4. [Configuration](#configuration)
5. [Data Sources & APIs](#data-sources--apis)
6. [Daily Workflow](#daily-workflow)
7. [File Structure](#file-structure)
8. [Confluence Scoring System](#confluence-scoring-system)
9. [SPY Magnet Logic](#spy-magnet-logic)
10. [Alert System](#alert-system)
11. [Customization Guide](#customization-guide)
12. [Troubleshooting](#troubleshooting)

---

## Overview

The **MNQ Trading Agent v2** is a Python-based multi-timeframe trading bot that:
- Monitors MNQ (Micro E-mini NASDAQ-100 futures) across 4 timeframes (1h, 30m, 15m, 5m)
- Detects liquidity sweeps (rejection signals at prior session levels)
- Analyzes multi-timeframe confluence and trend alignment
- Calculates trade probability using Claude AI
- Sends formatted alerts to Discord with trade assessments

**Key Philosophy:** Price is magnetically attracted to key levels. When price rejects liquidity at these levels, combined with multi-timeframe confluence, it signals high-probability setups.

### Core Workflow
```
Market Data (Tradovate) 
    ↓
Bar Close (15m or 5m) 
    ↓
Sweep Detection 
    ↓
Confluence Analysis 
    ↓
Claude Probability Assessment 
    ↓
Discord Alert
```

---

## Architecture

### Components

**1. Data Fetcher** (`data_fetcher.py`)
- Connects to Tradovate API
- Maintains rolling buffers of OHLCV bars for all timeframes
- Triggers callbacks on bar close (15m, 5m)
- Auto-reconnects on disconnection

**2. SPY Fetcher** (`spy_fetcher.py`)
- Fetches real-time SPY prices via Finnhub API
- Updates SPY price every second
- Provides price for SPY magnet proximity analysis

**3. Context Analyzer** (`context_analyzer.py`)
- Computes EMA trends per timeframe
- Detects liquidity sweeps at session levels
- Calculates timeframe alignment (how many TFs agree with sweep direction)
- Computes VWAP, POC (Point of Control), volume stats
- Returns comprehensive context dict for Claude

**4. Levels Analyzer** (`levels_analyzer.py`)
- Parses daily_levels.py (SPX/SPY key levels)
- Checks MNQ price proximity to SPX/SPY levels
- Verifies level file date is current (warns if outdated)
- Scores confluence based on pivot/level hits

**5. SPY Levels Analyzer** (`spy_levels_analyzer.py`)
- Distance-based magnet scoring (pivot attraction)
- Direction bonus (sweep aligns with SPY position vs pivot)
- Support/resistance analysis for other levels

**6. Probability Engine** (`probability_engine.py`)
- Builds comprehensive prompt for Claude Sonnet 4.5
- Sends context to Claude API
- Parses Claude's JSON response (assessment, probability, reasoning)
- Returns fallback assessment if API fails

**7. Discord Formatter** (`discord_formatter.py`)
- Formats all context as Discord embed fields
- Creates probability bar visualization
- Includes timeframe alignment, sweep details, market context
- Posts to webhook URL

**8. Agent** (`agent.py`)
- Main orchestrator
- Registers bar-close callback with data fetcher
- Calls all components in sequence
- Manages alert cooldown (no duplicate alerts within 5 min)
- Prints status every 60 seconds

---

## Core Features

### 1. Liquidity Sweep Detection

**What is a sweep?**
- Price wicks beyond a prior session high or low
- Closes back inside (rejection)
- Signals trapped liquidity being swept out

**Detection Logic:**
```python
# Short sweep: wick above high, close below
if bar.high >= level.high and bar.close < level.high:
    return SWEEP_FOUND

# Long sweep: wick below low, close above
if bar.low <= level.low and bar.close > level.low:
    return SWEEP_FOUND
```

**Trigger Timeframes:** 15m and 5m bars only (more reliable)

**Session Levels Used:**
- Prior Globex session highs/lows (last NUM_SESSIONS completed sessions)
- Computed from 1H bars for stability

---

### 2. Multi-Timeframe Alignment

**Concept:** Price tends to continue sweeps when multiple timeframes agree on direction.

**Calculation:**
- Compute EMA-based trend per TF (bull, bear, unknown)
- Count how many TFs trend matches sweep direction
- Require MIN_TF_ALIGNMENT (default 3/4) to proceed

**EMA Periods by Timeframe:**
- 1H: 50-period EMA
- 30m: 100-period EMA
- 15m: 100-period EMA
- 5m: 200-period EMA

**Example:**
```
Sweep: SHORT (down)
1H trend: BEAR ✓
30m trend: BEAR ✓
15m trend: BEAR ✓
5m trend: UNKNOWN
Result: 3/4 aligned → PASS
```

---

### 3. VWAP Proximity & POC

**VWAP (Volume-Weighted Average Price):**
- RTH-anchored (9:30 AM CT start)
- Resets daily
- Confluence when price near VWAP

**POC (Point of Control):**
- Most volume-traded price level in a session
- Calculated from volume profile (full session bars)
- Tracks last 5 completed Globex sessions
- Price attraction to POC is reliable

**Scoring:**
- Near POC (< 5 pts): +1 condition
- Near VWAP (< 3 pts): +0.5 condition (part of confluence)

---

### 4. Session Level Tracking

**What:** High/low of each completed Globex session

**Purpose:** Liquidity pools form at session extremes; price tends to return to them

**Calculation:**
- Uses 1H bars (fewer data points, captures true extremes)
- Tracks 10 completed sessions
- Builds "memory" of prior activity

**Time Zones:**
- RTH (Regular Trading Hours): 9:30 AM - 4:00 PM CT
- Globex (Electronic): 5:00 PM CT Sun - 4:00 PM CT Fri
- Database times in Eastern Time (automatic conversion)

---

## Configuration

### Main Config (`config.py`)

**API Keys & Endpoints:**
```python
PROJECTX_USERNAME = "your_username"          # TopstepX / ProjectX
PROJECTX_API_KEY = "your_api_key"
ANTHROPIC_API_KEY = "your_claude_api_key"
DISCORD_WEBHOOK_URL = "your_webhook"
FINNHUB_API_KEY = "your_finnhub_key"
```

**Trading Hours:**
```python
TIMEZONE = "America/Chicago"
RTH_START = (9, 30)         # 9:30 AM CT
RTH_END = (16, 0)           # 4:00 PM CT
GLOBEX_OPEN_HOUR = 17       # 5:00 PM CT
GLOBEX_CLOSE_HOUR = 16      # 4:00 PM CT
```

**Bar Buffers:**
```python
TIMEFRAMES = {
    "1h":  {"elementSize": 60,  "maxlen": 750,  "history_days": 30},
    "30m": {"elementSize": 30,  "maxlen": 1500, "history_days": 21},
    "15m": {"elementSize": 15,  "maxlen": 2000, "history_days": 21},
    "5m":  {"elementSize": 5,   "maxlen": 3000, "history_days": 14},
}

TRIGGER_TIMEFRAMES = ["15m", "5m"]      # Which TFs trigger alerts
MIN_TF_ALIGNMENT = 3                    # Must align on 3+ TFs
```

**Market Data Thresholds:**
```python
VOLUME_AVG_BARS = 20                    # Compute avg volume from last 20 bars
VOL_SPIKE_MULT = 1.5                    # Still calculates, not used in scoring
POC_PROXIMITY_PTS = 5.0                 # How close to POC counts
VWAP_PROXIMITY_PTS = 3.0                # How close to VWAP counts
TICK_SIZE = 0.25                        # MNQ tick
```

**Session Memory:**
```python
NUM_SESSIONS = 10                       # Track 10 prior sessions for H/L
POC_SESSIONS = 5                        # POC from last 5 completed sessions
```

**Alert Cooldown:**
```python
ALERT_COOLDOWN_SECS = 300              # No duplicate LONG/SHORT alerts within 5 min
```

**SPY Magnet Scoring:**
```python
SPY_PIVOT_MAGNET_THRESHOLDS = {
    'very_close': 0.30,    # Distance < 0.30 → +2.5 points
    'close':      1.00,    # Distance < 1.00 → +1.5 points
    'medium':     2.00,    # Distance < 2.00 → +1.0 points
    # >= 2.00 → +0.0 (no magnet)
}

SPY_OTHER_LEVELS_THRESHOLD = 0.30       # Only count other levels if within 0.30 pts
SPY_PIVOT_DIRECTION_BONUS = 0.5         # Extra if sweep direction aligns with SPY
```

---

## Data Sources & APIs

### 1. Tradovate (Market Data)

**Connection:**
- WebSocket RTC connection (real-time market data)
- ProjectX API for authentication

**Data Provided:**
- OHLCV bars across all 4 timeframes
- Live fills/balances (not currently used)

**Rate Limits:**
- No explicit per-call limits
- Connection-based (maintain persistent WebSocket)

### 2. Finnhub (SPY Price)

**Connection:**
- REST API, QUOTE endpoint
- Real-time quotes for SPY

**Data Provided:**
- Current SPY bid/ask/last price
- Updated every second

**Rate Limits:**
- Free tier: 60 API calls/min
- Recommended: 1 call/sec max (60/min)

### 3. Anthropic Claude API

**Connection:**
- REST API (claude-sonnet-4-5 model)
- Streaming disabled (full response wait)

**Data Provided:**
- Probability assessment (0-100%)
- Trade assessment (TAKE, HOLD, WATCH, PASS)
- Reasoning explanation
- Key risks
- TP/SL adjustments (parsed from response)

**Rate Limits:**
- Pricing-based (not call-limited)
- ~400k tokens/min (API tier dependent)

### 4. Discord Webhook

**Connection:**
- Simple HTTP POST to webhook URL
- No authentication (URL is the secret)

**Data Sent:**
- Formatted embed with all context
- One message per alert

**Rate Limits:**
- Per-webhook: 10 messages/10 sec (usually not hit)

---

## Daily Workflow

### Morning (Before Market Open)

1. **Update Daily Levels:**
   - Open `daily_levels.py`
   - Paste your key support/resistance levels (SPY and SPX)
   - Mark ONE level with `PIVOT` keyword (your key level)
   - Update DATE field to today's date (YYYY-MM-DD)
   - Save file

   Example:
   ```python
   DATE = "2026-06-05"
   
   SPY = """
   767.50
   764.30
   756.70 PIVOT
   753.60
   749.80
   """
   ```

2. **Start Agent:**
   ```bash
   python agent.py
   ```

3. **Verify Connections:**
   - Check log output for "All timeframe buffers ready"
   - Check for SPY price logging (e.g., "SPY price: 756.45")
   - Confirm Discord webhook URL is active

### During Market Hours

1. **Monitoring:**
   - Agent logs status every 60 seconds (MNQ price, SPY price, bar counts, connection status)
   - No action needed unless you see errors

2. **When Sweep Detected:**
   - Agent automatically checks alignment (3+ TF match required)
   - Calculates confluence score
   - Calls Claude for probability
   - Posts Discord alert

3. **Alert Cooldown:**
   - Only one LONG and one SHORT alert per 5 minutes
   - Prevents alert spam from multiple timeframe sweeps

### Date Check Alert

If you see this warning:
```
⚠️  PIVOT UPDATE NEEDED! ⚠️
   Loaded date: 2026-06-04
   Today's date: 2026-06-05
   The SPY/SPX levels may be OUTDATED.
   Please update daily_levels.py with today's levels before trading.
```

**Action:** Update `DATE` in `daily_levels.py` to today's date and refresh levels. Agent will continue but alert you on every sweep until fixed.

---

## File Structure

```
mnq_v2/
├── agent.py                    # Main orchestrator
├── config.py                   # All configuration constants
├── data_fetcher.py             # Tradovate WebSocket connection
├── spy_fetcher.py              # Finnhub SPY price fetcher
├── context_analyzer.py         # MTF analysis, sweep detection
├── levels_analyzer.py          # SPX/SPY level proximity & date checking
├── spy_levels_analyzer.py      # Pivot magnet scoring logic
├── probability_engine.py       # Claude API integration
├── discord_formatter.py        # Alert formatting
├── daily_levels.py             # Your daily key levels (UPDATE DAILY)
├── .env                        # API keys (DO NOT COMMIT)
├── .env.example                # Template for .env
├── SPY_MAGNET_LOGIC.md         # Detailed magnet scoring guide
├── AGENT_DOCUMENTATION.md      # This file
└── tests/
    ├── test_context_analyzer.py
    ├── test_discord_formatter.py
    ├── test_probability_engine.py
    ├── test_data_fetcher.py
    ├── fixtures.py
    └── ... (other test files)
```

---

## Confluence Scoring System

### Core Scoring (7 base conditions)

Each condition awards **+1 point** if TRUE:

1. **sweep_confirmed** — Liquidity sweep detected on trigger TF ✓ (always)
2. **reversal_candle** — Close rejection confirmed ✓ (always)
3. **near_poc** — Price within 5 pts of POC
4. **vwap_confluence** — Price on correct side of VWAP for direction
   - SHORT: price below VWAP
   - LONG: price above VWAP
5. **1h_trend_aligned** — 1H EMA trend matches sweep direction
6. **tf_3plus_aligned** — 3+ timeframes trend matches direction
7. **rth_session** — Alert fired during RTH (9:30 AM - 4:00 PM CT)

**Max base score: 7 points**

---

### External Conditions (3 conditions)

SPX/SPY level proximity (from `levels_analyzer.py`):

1. **near_spy_level** — Within proximity of any SPY level
2. **near_spx_level** — Within proximity of any SPX level  
3. **near_pivot** — Within proximity of SPY or SPX pivot

**Max external score: varies** (depends on level hits)

---

### SPY Magnet Score (separate, added to total)

Distance-based pivot attraction:

```
Pivot distance < 0.30 pts  → +2.5
Pivot distance < 1.00 pts  → +1.5
Pivot distance < 2.00 pts  → +1.0
Pivot distance >= 2.00 pts → +0.0

Direction bonus (if aligned) → +0.5
Other levels near (each)     → +0.5
```

---

### Total Confluence Score

**Formula:**
```
confluence_score = 
    base_score (0-7)
    + ext_score (0-3+ from SPX/SPY)
    + spy_magnet_score (0-3.5)
    + direction_bonus (0-0.5)
```

**Example with all conditions met:**
```
Base: 7/7
External: 2/3 (near SPY level + near pivot)
SPY magnet: 2.5 + 0.5 + 0.5 = 3.5
────────────
Total: 12.0 points (very strong setup)
```

---

### Claude's Probability Assessment

Claude receives the full context (trends, alignment, scores, etc.) and returns:

- **Probability:** 0-100% success estimate
- **Assessment:** 
  - **TAKE** — High probability, good setup
  - **HOLD** — Medium probability, wait for confluence
  - **WATCH** — Low probability, watch for reversal
  - **PASS** — Not recommended
- **Confidence:** low / medium / high
- **Reasoning:** Explanation of assessment
- **Key Risk:** Primary risk to the trade
- **TP_adjust:** Target multiplier (default 1.0)
- **SL_adjust:** Stop-loss multiplier (default 1.0)

---

## SPY Magnet Logic

### Concept

The pivot level acts as a **magnet** that attracts price regardless of which side (above/below) it's on. Distance decay scoring rewards proximity.

### Scoring Bands

```
Very Close (< 0.30 pts):  +2.5 points ███████████ (strongest)
Close (< 1.00 pts):       +1.5 points ██████
Medium (< 2.00 pts):      +1.0 points ███
Far (>= 2.00 pts):        +0.0 points (magnet worn off)
```

### Direction Bonus

**Extra +0.5 points** if sweep direction aligns with SPY position vs pivot:

- **LONG sweep + SPY above pivot** = bullish alignment ✓
- **SHORT sweep + SPY below pivot** = bearish alignment ✓
- **Opposite** = misaligned (still tradeable, less confluence)

### Other Levels

Levels besides the pivot are treated as **support/resistance zones**:
- Only count if within 0.30 pts of current SPY price
- Each hit contributes +0.5 points
- Rationale: Once you're away from the magnet pivot, nearby levels act as simple barriers

### Examples

**Example 1: SHORT Sweep, SPY 756.25 (PIVOT 756.40)**
```
Distance: 0.15 pts (very close)
Direction: Below pivot = bearish ✓

Score:
  Pivot magnet: +2.5 (very strong)
  Direction: +0.5 (aligned)
  Others: +0.0
  Total: +3.0
```

**Example 2: LONG Sweep, SPY 757.10 (PIVOT 756.40, 757.20 nearby)**
```
Distance from pivot: 0.70 pts (close)
Direction: Above pivot = bullish ✓
757.20 is 0.10 away = HIT

Score:
  Pivot magnet: +1.5 (strong)
  Direction: +0.5 (aligned)
  Others: +0.5 (757.20 support)
  Total: +2.5
```

---

## Alert System

### Discord Embed Format

Each alert contains these sections:

**1. Title & Probability**
```
MNQ SHORT — Liquidity Sweep @ 30440.50 (5m)
[██████████░░░░░░░░] 75% | High confidence
```

**2. Assessment**
- Bold verdict (TAKE / HOLD / WATCH / PASS)
- Claude's reasoning (1-2 sentences)

**3. Timeframe Alignment**
- Shows which TFs agree/disagree with sweep
- Example: "3/4 aligned (1H bear, 30m bear, 15m bear)"

**4. Sweep Details**
- Level price that was swept
- Level type (session high/low) and date
- Sweep size in points beyond level

**5. Market Context**
- VWAP level and distance
- POC level and distance
- Volume ratio to average (1.5x, 2.1x, etc.)

**6. Conditions Met**
- Checklist of all base conditions (7 total shown, each marked ✓ or ✗)
- Confluence score (e.g., "6/7 conditions met")

**7. SPX/SPY Levels** (if any hits)
- Which levels price is near
- Distance in points
- Price direction relative to level
- Score boost contribution

**8. Key Risk**
- Claude's assessment of primary risk

**9. Footer**
- Timestamp (CT)
- Source (Claude API)
- Disclaimer

### Alert Cooldown

- **Per direction:** LONG alerts separate from SHORT
- **Duration:** 300 seconds (5 minutes)
- **Purpose:** Prevent duplicate alerts from same sweep on different TFs

Example: If 5m bar closes with SHORT sweep, and 15m bar closes immediately after with same sweep, you get only ONE alert (not two).

### When Alerts Are Sent

Alerts fire when ALL of these are TRUE:
1. Sweep detected on 15m or 5m bar close
2. 3+ timeframes align with sweep direction
3. Cooldown period elapsed for that direction
4. No exceptions/errors in processing pipeline

---

## Customization Guide

### Adjusting Magnet Thresholds

Want to make the pivot "stickier"? Edit `config.py`:

```python
SPY_PIVOT_MAGNET_THRESHOLDS = {
    'very_close': 0.50,    # Increase from 0.30 for looser magnet
    'close':      1.50,    # Increase from 1.00 for wider range
    'medium':     3.00,    # Increase from 2.00 for longer influence
}
```

**Effect:** Price farther from pivot still gets magnet bonus

---

### Changing Confluence Requirements

Want stricter or looser alerts? Edit `config.py`:

```python
MIN_TF_ALIGNMENT = 4        # Changed from 3 — require ALL 4 TFs aligned (stricter)
MIN_TF_ALIGNMENT = 2        # Changed from 3 — only 2 TFs required (looser)
```

---

### Adjusting EMA Periods

Want faster/slower trend detection? Edit `config.py`:

```python
EMA_PERIODS = {
    "1h":  30,              # Decreased from 50 (faster, noisier)
    "30m": 50,              # Decreased from 100 (faster)
    "15m": 50,              # Decreased from 100
    "5m":  100,             # Decreased from 200 (faster)
}
```

**Effect:** Lower periods = faster trend changes (more alerts, possibly false signals)

---

### Changing Alert Cooldown

Want more or fewer alerts? Edit `config.py`:

```python
ALERT_COOLDOWN_SECS = 120   # Changed from 300 — 2 minutes between alerts (more frequent)
ALERT_COOLDOWN_SECS = 600   # Changed from 300 — 10 minutes (less frequent)
```

---

### Modifying Session Memory

Want more/fewer prior sessions tracked? Edit `config.py`:

```python
NUM_SESSIONS = 20           # Track 20 prior sessions (longer memory, larger buffer)
NUM_SESSIONS = 5            # Track 5 prior sessions (shorter memory, faster recency)
```

---

### Customizing Session Hours

If trading a different instrument or timeframe, adjust session boundaries:

```python
TIMEZONE = "America/New_York"   # Change from Chicago
RTH_START = (8, 30)             # Adjust from 9:30
RTH_END = (15, 0)               # Adjust from 16:00
```

---

## Troubleshooting

### Agent Won't Connect to Tradovate

**Symptom:** Log shows "Waiting for initial bar buffers" with no progress

**Solutions:**
1. Verify `PROJECTX_USERNAME` and `PROJECTX_API_KEY` in `.env`
2. Check that TopstepX account is active (not in paper/sim if expecting live data)
3. Verify MNQ symbol is available in your account
4. Check firewall/VPN blocking WebSocket port 443

**Test:**
```bash
python3 -c "from data_fetcher import MultiTimeframeFetcher; f = MultiTimeframeFetcher(); f.start(); import time; time.sleep(10); print(f.get_latest_price())"
```

---

### SPY Price Not Updating

**Symptom:** SPY shows 0.0 or stale value in logs

**Solutions:**
1. Verify `FINNHUB_API_KEY` in `.env`
2. Check free tier rate limit (60 calls/min max)
3. Verify network connectivity
4. Restart spy_fetcher

**Test:**
```bash
python3 -c "from spy_fetcher import SpyFetcher; f = SpyFetcher(); f.start(); import time; time.sleep(5); print(f.get_price())"
```

---

### Claude Probability Returns Fallback

**Symptom:** Log shows "fallback_on_api_error" with reason

**Solutions:**
1. Verify `ANTHROPIC_API_KEY` in `.env`
2. Check account has quota remaining
3. Verify prompt is valid JSON (check logs for "invalid json")
4. Check network connectivity to API

**Fallback Assessment:**
- Probability: 50%
- Assessment: WATCH
- Confidence: low
- Reasoning: "[error reason]"

---

### Discord Alerts Not Sending

**Symptom:** Agent processes sweep but no Discord message

**Solutions:**
1. Verify `DISCORD_WEBHOOK_URL` in `.env`
2. Confirm webhook URL is correct (paste in browser, should return 405 Method Not Allowed)
3. Check Discord channel still exists and webhook is active
4. Verify no firewall blocking Discord API

**Test:**
```bash
curl -X POST "YOUR_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"embeds":[{"title":"Test","description":"Testing webhook"}]}'
```

---

### Too Many Alerts / Alert Spam

**Symptoms:**
- Getting same sweep alert multiple times
- Alerts for weak setups

**Solutions:**
1. Increase `ALERT_COOLDOWN_SECS` in `config.py` (e.g., 600 instead of 300)
2. Increase `MIN_TF_ALIGNMENT` (e.g., 4 instead of 3) for stricter confluence
3. Manually edit `daily_levels.py` to reduce number of levels (fewer level hits = lower scores)

---

### Not Enough Alerts / Missing Setups

**Symptoms:**
- Sweeps happen but no alerts fire
- Confluence score too low

**Solutions:**
1. Decrease `MIN_TF_ALIGNMENT` to 2 (less strict)
2. Decrease `ALERT_COOLDOWN_SECS` to 120 (allow more frequent)
3. Adjust EMA periods lower for faster trend detection
4. Add more SPX/SPY levels to `daily_levels.py` (more confluence opportunities)
5. Review Claude's reasoning in logs — may be correctly filtering false signals

---

### Outdated Levels Warning

**Symptom:** "PIVOT UPDATE NEEDED!" warning appears on every sweep

**Solution:** Update `DATE` in `daily_levels.py` to today's date:
```python
DATE = "2026-06-05"  # Update to today
```

Save file and agent will reload automatically on next sweep (warning disappears).

---

### High CPU or Memory Usage

**Symptoms:**
- Agent using 50%+ CPU
- Memory slowly increasing

**Solutions:**
1. Reduce `maxlen` for each timeframe in `config.py` (lower buffer sizes)
   ```python
   "5m": {"elementSize": 5, "maxlen": 1000, ...}  # Reduced from 3000
   ```
2. Reduce `history_days` (less historical data fetched at startup)
3. Restart agent periodically (memory leaks in long-running connections)

---

## Command Reference

### Start Agent
```bash
python agent.py
```

### Run Tests
```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_context_analyzer.py -v

# Specific test
pytest tests/test_context_analyzer.py::TestDetectSweep::test_short_sweep_detected -v
```

### Check for Syntax Errors
```bash
python3 -m py_compile *.py
```

### View Logs (if redirected to file)
```bash
tail -f agent.log
```

---

## FAQ

**Q: Why does the agent require minimum 20 bars before starting?**
A: 20 bars provides sufficient historical context for EMA calculation and session level detection. Fewer bars = unreliable trends.

**Q: Can I trade other instruments besides MNQ?**
A: The agent is hardcoded for MNQ. To support other instruments, you'd need to:
1. Modify SPX/SPY conversion logic (assumes MNQ ≈ 4.7x SPX)
2. Adjust session hours if different market
3. Retrain EMA periods for the instrument's volatility

**Q: What if I want to use different SPY/SPX levels intraday?**
A: Edit `daily_levels.py` directly and save. Agent reloads on next sweep (or restart to reload immediately).

**Q: Does the agent place trades automatically?**
A: No. Agent only generates alerts and assessments. You must execute trades manually (TopstepX, Tradovate UI, or external integration).

**Q: Can I run multiple instances of the agent?**
A: Yes, but they'll share the same Tradovate connection (only one WebSocket). Use separate API keys for different accounts.

**Q: How accurate is Claude's probability estimate?**
A: Claude provides probabilistic guidance based on confluence context. Like any ML model, accuracy depends on:
- Quality of input features (confluence score is very important)
- Recent market regime
- Claude's training data relevance

Always treat as **probability estimate, not guaranteed outcome**.

**Q: Why no ATR-based TP/SL targets?**
A: Removed by design. ATR provides generic targets; you likely have better manual methods or risk management rules.

**Q: Why was volume spike removed from confluence?**
A: Volume alone is not as reliable as other factors. POC + volume profile analysis (which is kept) better captures volume significance.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    MARKET DATA SOURCES                      │
├─────────────────────────────────────────────────────────────┤
│  Tradovate API          Finnhub API         Anthropic API   │
│  (OHLCV bars 4TF)       (SPY price)         (Claude)        │
└──────────┬──────────────┬────────────────────┬──────────────┘
           │              │                    │
           ↓              ↓                    ↓
    ┌──────────────┐ ┌───────────┐  ┌──────────────────┐
    │ DataFetcher  │ │ SpyFetcher│  │ ProbabilityEngine│
    │ (WebSocket)  │ │ (REST)    │  │ (REST)          │
    └──────┬───────┘ └─────┬─────┘  └────────┬─────────┘
           │               │                 │
           └───────────────┼─────────────────┘
                           ↓
            ┌──────────────────────────────┐
            │    Agent (Orchestrator)      │
            ├──────────────────────────────┤
            │ 1. Await bar close           │
            │ 2. Build MTF context         │
            │ 3. Analyze levels proximity  │
            │ 4. Calculate confluence      │
            │ 5. Call Claude               │
            │ 6. Format alert              │
            │ 7. Send Discord              │
            └──────────────────────────────┘
                     │      │
        ┌────────────┼──────┴──────────┐
        │            │                 │
        ↓            ↓                 ↓
┌──────────────┐ ┌────────────┐ ┌──────────────┐
│ContextAnalyz│ │LevelsAnalyz│ │SpyMagnetAnalyz│
│ (Sweep, MTF)│ │(SPX/SPY)   │ │(Pivot magnet) │
└──────────────┘ └────────────┘ └──────────────┘
        │            │                 │
        └────────────┼─────────────────┘
                     ↓
            ┌──────────────────────┐
            │ DiscordFormatter     │
            │ (Embed building)     │
            └──────────────────────┘
                     │
                     ↓
            ┌──────────────────────┐
            │ Discord Webhook      │
            │ (HTTP POST)          │
            └──────────────────────┘
```

---

## Summary

The MNQ Trading Agent v2 is a sophisticated multi-timeframe trading system built around three core insights:

1. **Liquidity sweeps** at session extremes signal rejection and potential reversals
2. **Multi-timeframe confluence** dramatically increases reliability
3. **Price attraction to key levels** (especially pivot) provides additional context for probability assessment

The system is:
- **Modular:** Each component has a single responsibility
- **Configurable:** Almost every parameter can be tuned
- **Testable:** 78+ unit tests cover core logic
- **Transparent:** All decisions are logged and visible
- **Safe:** No automatic trade execution (alerts only)

For best results:
- Update levels daily before session starts
- Monitor logs for errors/warnings
- Adjust configuration based on your risk tolerance and market regime
- Use Claude's assessment as guidance, not gospel
- Validate with your own risk management rules

Good trading!

---

**Document Version:** 2.0  
**Last Updated:** 2026-06-05  
**Agent Version:** v2  
