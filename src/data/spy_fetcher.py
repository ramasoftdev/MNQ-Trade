"""
SPY Price Fetcher via Finnhub
==============================
Polls real-time SPY price every 10 seconds.
Checks proximity to key levels from daily_levels.py.
"""

import requests
import logging
import threading
import time
from src.data.config import FINNHUB_API_KEY, FINNHUB_BASE_URL

log = logging.getLogger("spy_fetcher")


class SpyFetcher:
    """Polls Finnhub for real-time SPY quote."""

    def __init__(self):
        self.price = 0.0
        self.high = 0.0
        self.low = 0.0
        self.bid = 0.0
        self.ask = 0.0
        self.timestamp = None
        self._lock = threading.Lock()
        self._stop = False
        self.connected = False

    def get_price(self) -> float:
        """Get current SPY price."""
        with self._lock:
            return self.price

    def get_quote(self) -> dict:
        """Get full SPY quote snapshot."""
        with self._lock:
            return {
                "price": self.price,
                "high": self.high,
                "low": self.low,
                "bid": self.bid,
                "ask": self.ask,
            }

    def is_near_level(self, level: float, threshold: float = 0.30) -> bool:
        """Check if SPY is within threshold of a level."""
        return abs(self.get_price() - level) <= threshold

    def start(self):
        """Start polling SPY price in background thread."""

        def run():
            log.info("SPY fetcher started (Finnhub)")
            while not self._stop:
                try:
                    self._poll()
                    time.sleep(10)  # Poll every 10 seconds
                except Exception as e:
                    log.warning(f"SPY fetch error: {e} — retrying in 30s")
                    self.connected = False
                    time.sleep(30)

        t = threading.Thread(target=run, daemon=True)
        t.start()

    def stop(self):
        """Stop polling."""
        self._stop = True

    def _poll(self):
        """Fetch latest SPY quote from Finnhub."""
        resp = requests.get(
            f"{FINNHUB_BASE_URL}/quote",
            params={"symbol": "SPY", "token": FINNHUB_API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if "c" not in data or data["c"] == 0:
            log.warning("Finnhub returned invalid quote")
            self.connected = False
            return

        with self._lock:
            self.price = data.get("c", 0.0)
            self.high = data.get("h", 0.0)
            self.low = data.get("l", 0.0)
            self.bid = data.get("bp", 0.0)
            self.ask = data.get("ap", 0.0)
            self.timestamp = data.get("t", None)
            self.connected = True

        log.debug(f"SPY quote: {self.price:.2f} (bid={self.bid:.2f} ask={self.ask:.2f})")
