"""
Component 2 — Multi-Timeframe Data Fetcher (ProjectX / TopstepX Edition)
=========================================================================
Replaces Tradovate WebSocket with ProjectX REST API.

Architecture:
  1. Authenticate with username + API key → JWT session token (valid 24h)
  2. Search for active MNQ contract → get contractId (e.g. CON.F.US.MNQ.M6)
  3. Load historical bars for each TF via POST /api/History/retrieveBars
  4. Poll for new bars periodically to detect bar closes
  5. When a trigger TF (15m or 5m) bar closes → fire on_bar_close callback
  6. Auto re-authenticate before token expires (every 23 hours)

Rate limits (respected):
  - retrieveBars: 50 req / 30s
  - Poll schedule: 5m every 10s, 15m every 30s, 30m every 60s, 1h every 120s
"""

import json
import time
import threading
import logging
import requests
import pytz
from datetime import datetime, timedelta
from collections import deque
from src.data.config import (
    PROJECTX_USERNAME, PROJECTX_API_KEY,
    PROJECTX_BASE_URL, PROJECTX_LIVE,
    MNQ_SYMBOL, TIMEFRAMES, TRIGGER_TIMEFRAMES,
)

log = logging.getLogger("data_fetcher")

# Bar unit code — Minute = 2
UNIT_MINUTE = 2

# Poll interval per timeframe (seconds)
POLL_INTERVAL = {
    "5m":  10,
    "15m": 30,
    "30m": 60,
    "1h":  120,
}


class MultiTimeframeFetcher:

    def __init__(self):
        # Per-TF bar buffers (deque, oldest first)
        self._buffers: dict = {
            tf: deque(maxlen=cfg["maxlen"]) for tf, cfg in TIMEFRAMES.items()
        }
        # Latest known bar timestamp per TF (used for close detection)
        self._last_ts: dict = {tf: None for tf in TIMEFRAMES}

        # Auth state
        self.access_token: str = None
        self.token_time: datetime = None

        # Contract info
        self.contract_id: str = None   # e.g. CON.F.US.MNQ.M6
        self.symbol_id:   str = None   # e.g. F.US.MNQ

        self.connected: bool = False
        self._lock = threading.Lock()
        self._stop  = False

        # Callback: on_bar_close(tf: str, bars: list) -> None
        self._bar_close_cb = None

    # ── Public interface ───────────────────────────────────

    def set_bar_close_callback(self, fn):
        self._bar_close_cb = fn

    def get_bars(self, tf: str) -> list:
        with self._lock:
            return list(self._buffers[tf])

    def get_all_bars(self) -> dict:
        with self._lock:
            return {tf: list(buf) for tf, buf in self._buffers.items()}

    def get_latest_price(self) -> float:
        with self._lock:
            for tf in ["5m", "15m", "30m", "1h"]:
                buf = self._buffers[tf]
                if buf:
                    return buf[-1]["close"]
        return 0.0

    def is_ready(self, min_bars: int = 20) -> bool:
        with self._lock:
            return all(len(buf) >= min_bars for buf in self._buffers.values())

    def wait_for_data(self, min_bars: int = 20, timeout: int = 120) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            if self.is_ready(min_bars):
                return True
            time.sleep(2)
        return False

    def start(self):
        """Authenticate, find contract, load history, then start polling threads."""
        def run():
            while not self._stop:
                try:
                    self._authenticate()
                    self._find_contract()
                    self._load_all_history()
                    self.connected = True
                    log.info("Initial bar buffers loaded. Starting poll loops.")
                    self._start_poll_threads()
                    # Keep main run thread alive; check for token refresh
                    while not self._stop:
                        time.sleep(60)
                        if self._token_needs_refresh():
                            log.info("Token nearing expiry — re-authenticating.")
                            self._authenticate()
                except Exception as e:
                    log.error(f"Data fetcher error: {e} — retrying in 15s")
                    self.connected = False
                    time.sleep(15)

        threading.Thread(target=run, daemon=True).start()
        log.info("Multi-timeframe data fetcher started (ProjectX).")

    # ── Authentication ─────────────────────────────────────

    def _authenticate(self):
        """POST /api/Auth/loginKey → get JWT token."""
        log.info("Authenticating with ProjectX...")
        resp = requests.post(
            f"{PROJECTX_BASE_URL}/api/Auth/loginKey",
            json={"userName": PROJECTX_USERNAME, "apiKey": PROJECTX_API_KEY},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"ProjectX auth failed: {data.get('errorMessage')}")
        self.access_token = data["token"]
        self.token_time   = datetime.utcnow()
        log.info("ProjectX auth OK. Token valid for 24h.")

    def _token_needs_refresh(self) -> bool:
        if not self.token_time:
            return True
        age = (datetime.utcnow() - self.token_time).total_seconds()
        return age > 82800  # 23 hours

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type":  "application/json",
            "accept":        "text/plain",
        }

    # ── Contract discovery ─────────────────────────────────

    def _find_contract(self):
        """Search for active MNQ contract and store its ID."""
        log.info(f"Searching for active {MNQ_SYMBOL} contract...")
        resp = requests.post(
            f"{PROJECTX_BASE_URL}/api/Contract/search",
            headers=self._headers(),
            json={"searchText": MNQ_SYMBOL, "live": PROJECTX_LIVE},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"Contract search failed: {data.get('errorMessage')}")

        contracts = data.get("contracts", [])
        # Find Micro E-mini Nasdaq (MNQ), not NQ
        for c in contracts:
            desc = c.get("description", "")
            if "Micro E-mini Nasdaq" in desc and c.get("activeContract"):
                self.contract_id = c["id"]
                self.symbol_id   = c["symbolId"]
                log.info(f"Contract found: {c['name']} — {desc} — id={self.contract_id}")
                return

        # Fallback: take first result with MNQ in name
        for c in contracts:
            if "MNQ" in c.get("name", "") and c.get("activeContract"):
                self.contract_id = c["id"]
                self.symbol_id   = c["symbolId"]
                log.warning(f"Using fallback contract: {c['name']} id={self.contract_id}")
                return

        raise RuntimeError(
            f"No active MNQ contract found. Available: {[c['name'] for c in contracts]}"
        )

    # ── Historical bar loading ─────────────────────────────

    def _fetch_bars(self, unit_minutes: int, history_days: int,
                    limit: int, include_partial: bool = False) -> list:
        """
        Fetch historical OHLCV bars via POST /api/History/retrieveBars.
        Returns list of bar dicts sorted oldest → newest.
        """
        end_time   = datetime.utcnow()
        start_time = end_time - timedelta(days=history_days)

        resp = requests.post(
            f"{PROJECTX_BASE_URL}/api/History/retrieveBars",
            headers=self._headers(),
            json={
                "contractId":        self.contract_id,
                "live":              PROJECTX_LIVE,
                "startTime":         start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "endTime":           end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "unit":              UNIT_MINUTE,
                "unitNumber":        unit_minutes,
                "limit":             limit,
                "includePartialBar": include_partial,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"retrieveBars failed: {data.get('errorMessage')}")

        bars = []
        # API returns newest first — reverse to get oldest first
        for b in reversed(data.get("bars", [])):
            # Parse ISO timestamp (e.g. "2024-12-20T14:00:00+00:00")
            ts_str = b["t"].replace("+00:00", "").replace("Z", "")
            ts = datetime.fromisoformat(ts_str).replace(tzinfo=pytz.utc)
            bars.append({
                "timestamp": ts,
                "open":      float(b["o"]),
                "high":      float(b["h"]),
                "low":       float(b["l"]),
                "close":     float(b["c"]),
                "volume":    float(b["v"]),
            })
        return bars

    def _load_all_history(self):
        """Load historical bars for all 4 timeframes on startup."""
        for tf, cfg in TIMEFRAMES.items():
            log.info(f"Loading {tf} history ({cfg['history_days']} days)...")
            try:
                bars = self._fetch_bars(
                    unit_minutes  = cfg["elementSize"],
                    history_days  = cfg["history_days"],
                    limit         = cfg["maxlen"],
                    include_partial = False,
                )
                with self._lock:
                    self._buffers[tf].clear()
                    for bar in bars:
                        self._buffers[tf].append(bar)
                    if bars:
                        self._last_ts[tf] = bars[-1]["timestamp"]
                log.info(f"  {tf}: loaded {len(bars)} bars.")
                # Small delay to respect rate limits
                time.sleep(0.7)
            except Exception as e:
                log.error(f"Failed to load {tf} history: {e}")

    # ── Polling threads ────────────────────────────────────

    def _start_poll_threads(self):
        """Start one polling thread per timeframe."""
        for tf in TIMEFRAMES:
            t = threading.Thread(
                target=self._poll_loop,
                args=(tf,),
                daemon=True,
                name=f"poll-{tf}",
            )
            t.start()

    def _poll_loop(self, tf: str):
        """
        Periodically fetch the latest bars (+ partial) for this TF.
        If the latest closed bar has a new timestamp → bar closed → fire callback.
        """
        cfg      = TIMEFRAMES[tf]
        interval = POLL_INTERVAL[tf]

        log.info(f"Poll loop started for {tf} (every {interval}s)")

        while not self._stop:
            time.sleep(interval)
            if not self.access_token:
                continue
            try:
                # Fetch latest bars + partial
                bars = self._fetch_bars(
                    unit_minutes    = cfg["elementSize"],
                    history_days    = 2,
                    limit           = 5,
                    include_partial = True,
                )

                if not bars:
                    log.warning(f"[{tf}] poll returned no bars")
                    continue

                # Partial bar is last — closed bars are everything before it
                closed_bars = bars[:-1] if len(bars) > 1 else bars
                partial_bar = bars[-1] if len(bars) > 1 else None
                if not closed_bars:
                    continue

                latest_closed = closed_bars[-1]
                latest_ts     = latest_closed["timestamp"]

                # Log every poll with current price info
                ts_str = latest_closed["timestamp"].strftime("%H:%M")
                if partial_bar:
                    cur_price = partial_bar["close"]
                    cur_high  = partial_bar["high"]
                    cur_low   = partial_bar["low"]
                    cur_vol   = int(partial_bar["volume"])
                    log.info(
                        f"[{tf}]  poll → closed={ts_str}  "
                        f"live price={cur_price:.2f}  "
                        f"H={cur_high:.2f} L={cur_low:.2f}  vol={cur_vol}"
                    )
                else:
                    log.info(f"[{tf}]  poll → closed={ts_str}  close={latest_closed['close']:.2f}")

                with self._lock:
                    prev_ts = self._last_ts[tf]

                if prev_ts is None or latest_ts > prev_ts:
                    # New bar(s) detected
                    with self._lock:
                        for bar in closed_bars:
                            if self._last_ts[tf] is None or bar["timestamp"] > self._last_ts[tf]:
                                self._buffers[tf].append(bar)
                        self._last_ts[tf] = latest_ts
                        bars_snapshot = list(self._buffers[tf])

                    # Detailed closed bar log
                    b = latest_closed
                    log.info(
                        f"[{tf}] ✦ NEW BAR CLOSED {b['timestamp'].strftime('%H:%M')}  "
                        f"O={b['open']:.2f}  H={b['high']:.2f}  "
                        f"L={b['low']:.2f}  C={b['close']:.2f}  "
                        f"V={int(b['volume'])}  "
                        f"buffer={len(bars_snapshot)}"
                    )

                    # Fire callback for trigger timeframes
                    if tf in TRIGGER_TIMEFRAMES and self._bar_close_cb:
                        log.info(f"[{tf}] → firing sweep detection pipeline...")
                        threading.Thread(
                            target=self._bar_close_cb,
                            args=(tf, bars_snapshot),
                            daemon=True,
                        ).start()
                else:
                    log.info(f"[{tf}]  no new bar (last closed={latest_ts.strftime('%H:%M')})")

                # Always update the partial (current) bar for get_latest_price()
                if len(bars) > 0:
                    partial = bars[-1]
                    with self._lock:
                        # Store partial bar without committing — just for price
                        self._buffers[tf]  # touch to keep alive

            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    log.warning(f"{tf} rate limited — backing off 30s")
                    time.sleep(30)
                elif e.response is not None and e.response.status_code in (401, 403):
                    log.warning(f"{tf} token expired — re-authenticating")
                    try:
                        self._authenticate()
                    except Exception as auth_err:
                        log.error(f"Re-auth failed: {auth_err}")
                else:
                    log.error(f"{tf} poll error: {e}")
            except Exception as e:
                log.error(f"{tf} poll unexpected error: {e}")
