# MNQ Trading Agent v2 — Multi-Timeframe Edition

## Overview

A standalone Python agent that monitors MNQ (Micro E-mini Nasdaq-100) for liquidity sweeps across 4 timeframes. When a sweep is detected with 3+ timeframe alignment, it calls Claude API for probability assessment and sends alerts to Discord.

**No Pine Script. No webhooks. No servers. Just pure Python bar monitoring.**

---

## How it works

1. **Authenticates** with ProjectX (TopstepX API) → gets access token
2. **Finds active MNQ contract** (auto-detects month)
3. **Loads 30 days of history** for 1H, 30m, 15m, 5m bars
4. **Polls every 10-120 seconds** for new bars per timeframe
5. **On 15m/5m bar close** → runs sweep detection
6. **If sweep + 3/4 TF alignment** → calls Claude + sends Discord alert
7. **Monitors SPY price** independently via Finnhub

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

Requires:
- `requests` — ProjectX API calls
- `python-dotenv` — load .env credentials
- `anthropic` — Claude API

### 2. Create `.env` file
Copy from `.env.example`:
```
PROJECTX_USERNAME=your_topstepx_email@example.com
PROJECTX_API_KEY=your_api_key
ANTHROPIC_API_KEY=sk-ant-...
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
FINNHUB_API_KEY=your_finnhub_key
```

**Never commit `.env` to git** — it's in `.gitignore`

### 3. Run the agent
```bash
python agent.py
```

**Output:**
```
============================================================
  MNQ Trading Agent v2 — Multi-Timeframe Edition
  Trigger TFs : 15m, 5m
  Min alignment: 3/4 timeframes
  Alert cooldown: 300s
============================================================
19:22:06  INFO      data_fetcher  Authenticating with ProjectX...
19:22:07  INFO      data_fetcher  ProjectX auth OK. Token valid for 24h.
19:22:07  INFO      data_fetcher  Contract found: MNQM6
19:22:07  INFO      data_fetcher  Loading 1h history (30 days)...
...
All timeframe buffers ready. Monitoring for sweeps...
```

---

## Daily workflow

Each morning before session open:

1. Update `daily_levels.py` with today's SPY key levels
2. Mark the pivot with the word **PIVOT** in the string
3. Save — agent reloads on next alert
4. Monitor Discord for alerts

---

## Architecture

| Module | Purpose |
|---|---|
| `agent.py` | Main entry point, bar-close callbacks, alert pipeline |
| `data_fetcher.py` | ProjectX authentication, bar polling, buffer management |
| `spy_fetcher.py` | Finnhub integration, real-time SPY price |
| `context_analyzer.py` | Sweep detection, confluence scoring, multi-TF analysis |
| `probability_engine.py` | Claude API integration for probability assessment |
| `discord_formatter.py` | Rich embed formatting, webhook send |
| `config.py` | All tunable parameters (loads from .env) |
| `daily_levels.py` | Manual SPY/SPX key levels (update daily) |

---

## Tuning

| Setting | File | Default | Impact |
|---|---|---|---|
| `TRIGGER_TIMEFRAMES` | config.py | [15m, 5m] | Which TF bar closes fire alerts |
| `MIN_TF_ALIGNMENT` | config.py | 3 | Min TFs that must agree (1-4) |
| `ALERT_COOLDOWN_SECS` | config.py | 300 | Seconds between same-direction alerts |
| `VOL_SPIKE_MULT` | config.py | 1.5 | Volume must be 1.5x average to count |
| `VWAP_PROXIMITY_PTS` | config.py | 3.0 | How close to VWAP to count as "near" |

Lower `MIN_TF_ALIGNMENT` = more alerts, lower quality  
Higher `VOL_SPIKE_MULT` = fewer alerts, higher conviction

---

## What you see in Discord

```
MNQ SHORT ▼ — Liquidity Sweep @ 30440.50  (5M)
TAKE ✅ — 72% probability

Score: 8/10 | TFs: 3/4 aligned
TP: -12pts  SL: +6pts  R:R: 2:1
SPY at PIVOT zone ★
```

---

## Logs

Watch the terminal for real-time activity:

```
[5m]  poll → closed=14:25  live price=30444.50  H=30451.25 L=30440.00  vol=2104
[5m] ✦ NEW BAR CLOSED 14:30  O=30444.50  H=30451.25  L=30440.00  C=30448.75  V=2104  buffer=2713
[5m] → firing sweep detection pipeline...

Bar closed on 5m (2713 bars in buffer)
  SPY: 456.25
SWEEP on 5m: SHORT @ 30440.50 (level=30450 sweep_size=5.0pts)
Sweep found on 5m (SHORT) but only 2/4 TFs aligned (need 3) — skipping.

STATUS  MNQ=30444.50  SPY=456.25  bars 1h=502 30m=682 15m=1364 5m=2712  MNQ_connected=True  SPY_connected=True
```

---

## Rate limits respected

- **ProjectX**: 50 bar requests / 30 seconds (we use ~9/min)
- **Finnhub**: Free tier limits (we poll every 10s)
- **Anthropic**: 50 requests/min (we call on alerts only, ~5-10/day)
- **Discord**: 30 requests / 60s (we send 1-2/min max)

All within safe limits for a single agent instance.

---

## Troubleshooting

| Issue | Check |
|---|---|
| "auth failed" | `PROJECTX_USERNAME` / `PROJECTX_API_KEY` correct in `.env`? |
| "Contract not found" | Is the contract active? (contracts roll monthly: M=Jun, U=Sep, Z=Dec, H=Mar) |
| "No bars returned" | Contract month correct? Network connection OK? |
| "SPY price = 0" | Finnhub API key valid? Market hours? |
| "Discord send failed" | Webhook URL correct? Not expired? |
| "Rate limited (429)" | API quota exceeded. Agent auto-backs off 30s. |

---

## Next steps

1. **Trade Journal** — log each alert, track win rate
2. **Daily Report** — end-of-day summary to Discord
3. **Position sizing** — auto-calculate shares based on risk
4. **Performance metrics** — backtest confluence thresholds

---

**Author:** Adrian  
**Last updated:** 2026-06-04  
**Status:** Live monitoring only (no auto-execution)
