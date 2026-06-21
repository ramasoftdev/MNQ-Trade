"""Price service for fetching market data via Finnhub REST API."""

import logging
import requests
from typing import Optional

from src.data.config import FINNHUB_API_KEY, FINNHUB_BASE_URL

log = logging.getLogger("price_service")


class PriceService:
    """Handles fetching current market prices via Finnhub API."""

    def __init__(self):
        self.api_key = FINNHUB_API_KEY
        self.base_url = FINNHUB_BASE_URL

    def get_mnq_price(self) -> Optional[float]:
        """
        Fetch current MNQ (Micro E-mini Nasdaq-100) price.

        Returns:
            Current price or None if fetch fails
        """
        return self.get_price("MNQ")

    def get_spy_price(self) -> Optional[float]:
        """
        Fetch current SPY price.

        Returns:
            Current price or None if fetch fails
        """
        return self.get_price("SPY")

    def get_spx_price(self) -> Optional[float]:
        """
        Fetch current SPX price.

        Returns:
            Current price or None if fetch fails
        """
        return self.get_price("^GSPC")

    def get_price(self, symbol: str) -> Optional[float]:
        """
        Fetch price for any symbol via Finnhub REST API.

        Args:
            symbol: Stock/futures symbol

        Returns:
            Current price or None if fetch fails
        """
        try:
            url = f"{self.base_url}/quote"
            params = {
                "symbol": symbol,
                "token": self.api_key
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data and "c" in data:
                price = data["c"]
                log.debug(f"{symbol} price: {price:.2f}")
                return price
            else:
                log.warning(f"Invalid {symbol} quote response: {data}")
                return None
        except Exception as e:
            log.error(f"Failed to fetch {symbol} price: {e}")
            return None
