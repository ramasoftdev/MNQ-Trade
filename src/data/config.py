"""
MNQ Trading Agent v2 — Configuration
======================================
All secrets are loaded from .env — never hardcoded here.
Copy .env.example → .env and fill in your values.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (3 levels up from this file: src/data/config.py)
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)

# ── ProjectX / TopstepX ───────────────────────────────────────
PROJECTX_USERNAME   = os.getenv("PROJECTX_USERNAME", "")
PROJECTX_API_KEY    = os.getenv("PROJECTX_API_KEY",  "")
PROJECTX_BASE_URL   = "https://api.topstepx.com"
PROJECTX_RTC_URL    = "wss://rtc.topstepx.com/hubs/market"
PROJECTX_LIVE       = False   # False = sim/eval account, True = live funded

# MNQ symbol search text — agent auto-finds the active contract
MNQ_SYMBOL          = "MNQ"

# ── Anthropic ─────────────────────────────────────────────────
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL        = "claude-sonnet-4-5"

# ── Discord ───────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# ── Finnhub (SPY price data) ───────────────────────────────────
FINNHUB_API_KEY     = os.getenv("FINNHUB_API_KEY", "")
FINNHUB_BASE_URL    = "https://finnhub.io/api/v1"

# ── Session boundaries ────────────────────────────────────────
TIMEZONE            = "America/Chicago"
RTH_START           = (9, 30)
RTH_END             = (16, 0)
GLOBEX_OPEN_HOUR    = 17
GLOBEX_CLOSE_HOUR   = 16

# ── Multi-timeframe settings ──────────────────────────────────
TIMEFRAMES = {
    "1d":  {"elementSize": 1440, "maxlen": 250, "history_days": 250},  # Daily bars
    "15m": {"elementSize": 15,   "maxlen": 2000, "history_days": 21},
    "5m":  {"elementSize": 5,    "maxlen": 3000, "history_days": 14},
}

TRIGGER_TIMEFRAMES  = ["5m"]  # Primary entry on 5m
CONFIRMATION_TF     = "15m"   # Confirmation on 15m

# ── NEW SYSTEM: VWAP/POC Configuration ────────────────────────
# Entry Signal: 5m VWAP bounce with volume confirmation
# Confirmation: 15m MA alignment (bullish or bearish)
# Context: Daily MA levels for macro analysis

# MA Periods for all timeframes
MA_PERIODS = {
    "5m":  [5, 20, 50],        # Entry timeframe MAs
    "15m": [5, 20, 50],        # Confirmation timeframe MAs
    "1d":  [5, 20, 50]         # Daily macro context
}

# VWAP Bounce Detection Settings
VWAP_TOLERANCE_PTS        = 5.0      # Price within X pts of VWAP to count as "near"
VWAP_REVERSAL_BODY_RATIO  = 0.5      # Reversal candle body must be 50%+ of range
VWAP_BOUNCE_CONFIDENCE    = 60       # Minimum confidence for bounce (0-100)

# Volume Settings
VOLUME_LOOKBACK_BARS      = 5        # Bars to use for average volume
VOLUME_SPIKE_MULTIPLIER   = 1.2      # Current volume > avg × 1.2 = spike
POC_LOOKBACK_BARS         = 24       # Bars to analyze for POC calculation

# MA Alignment & Support/Resistance
MA_ALIGNMENT_TOLERANCE    = 2.0      # Distance between MAs to be considered "aligned"
MA_SUPPORT_RESISTANCE_TOL = 15.0     # Price within X pts to classify as support/resistance

# Confluence Scoring (VWAP/POC System)
# Maximum possible: 10 points
CONFLUENCE_THRESHOLD      = 6        # Minimum score to generate alert
CONFLUENCE_MAX            = 10       # Maximum possible score

# Confluence Score Breakdown:
# VWAP bounce: +3 pts
# Volume spike: +2 pts
# 15m MA aligned (bullish/bearish): +2 pts
# POC proximity: +1 pt
# MA5 proximity (15m): +1 pt
# ───────────────────────────────────
# Total: 10 pts

# ── Alert cooldown ────────────────────────────────────────────
ALERT_COOLDOWN_SECS = 300

# ── Legacy settings (kept for compatibility) ─────────────────
TICK_SIZE           = 0.25
NUM_SESSIONS        = 10
POC_SESSIONS        = 5

# ── SPY Magnet Level Thresholds ───────────────────────────
# Pivot acts as magnet — distance-based scoring
SPY_PIVOT_MAGNET_THRESHOLDS = {
    'very_close': 0.30,    # Distance < 0.30 → +2.0 points (strongest magnet)
    'close':      1.00,    # Distance < 1.00 → +1.0 points
    'medium':     2.00,    # Distance < 2.00 → +0.5 points
    # Distance >= 2.00 → +0.0 points (magnet effect too weak)
}

SPY_OTHER_LEVELS_THRESHOLD = 0.30  # Only count other levels if within 0.30 pts

SPY_PIVOT_DIRECTION_BONUS = 0.5  # Extra points if sweep direction aligns with SPY position vs pivot

# ── Trade Journal & Reports ──────────────────────────────
TRADE_JOURNAL_DB = "trades.db"          # SQLite database for alerts & trades
DAILY_REPORT_TIME = (16, 5)             # Generate daily report at 4:05 PM CT (after market close)
DAILY_REPORT_DISCORD_WEBHOOK = DISCORD_WEBHOOK_URL  # Send report to same Discord webhook
