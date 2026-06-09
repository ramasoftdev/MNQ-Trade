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
    "1h":  {"elementSize": 60, "maxlen": 750,  "history_days": 30},
    "30m": {"elementSize": 30, "maxlen": 1500, "history_days": 21},
    "15m": {"elementSize": 15, "maxlen": 2000, "history_days": 21},
    "5m":  {"elementSize": 5,  "maxlen": 3000, "history_days": 14},
}

TRIGGER_TIMEFRAMES  = ["15m", "5m"]
MIN_TF_ALIGNMENT    = 3

EMA_PERIODS = {
    "1h":  50,
    "30m": 100,
    "15m": 100,
    "5m":  200,
}

# ── Alert cooldown ────────────────────────────────────────────
ALERT_COOLDOWN_SECS = 300

# ── Market data thresholds ────────────────────────────────────
VOLUME_AVG_BARS     = 20
VOL_SPIKE_MULT      = 1.5  # Volume spike detection still computes, but NOT used in confluence scoring
POC_PROXIMITY_PTS   = 5.0
VWAP_PROXIMITY_PTS  = 3.0
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
