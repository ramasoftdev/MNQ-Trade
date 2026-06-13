"""Price service for fetching market data."""

import logging
from typing import Optional

from src.data.config import get_finnhub_client

log = logging.getLogger("price_service")


class PriceService:
    """Handles fetching current market prices."""

    def __init__(self):
        self.finnhub = get_finnhub_client()

    def get_mnq_price(self) -> Optional[float]:
        """
        Fetch current MNQ (Micro E-mini Nasdaq-100) price.

        Returns:
            Current price or None if fetch fails
        """
        try:
            quote = self.finnhub.quote("MNQ")
            if quote and "c" in quote:
                price = quote["c"]
                log.debug(f"MNQ price: {price:.2f}")
                return price
            else:
                log.warning(f"Invalid MNQ quote response: {quote}")
                return None
        except Exception as e:
            log.error(f"Failed to fetch MNQ price: {e}")
            return None

    def get_spy_price(self) -> Optional[float]:
        """
        Fetch current SPY price.

        Returns:
            Current price or None if fetch fails
        """
        try:
            quote = self.finnhub.quote("SPY")
            if quote and "c" in quote:
                price = quote["c"]
                log.debug(f"SPY price: {price:.2f}")
                return price
            else:
                log.warning(f"Invalid SPY quote response: {quote}")
                return None
        except Exception as e:
            log.error(f"Failed to fetch SPY price: {e}")
            return None

    def get_spx_price(self) -> Optional[float]:
        """
        Fetch current SPX price.

        Returns:
            Current price or None if fetch fails
        """
        try:
            quote = self.finnhub.quote("^GSPC")
            if quote and "c" in quote:
                price = quote["c"]
                log.debug(f"SPX price: {price:.2f}")
                return price
            else:
                log.warning(f"Invalid SPX quote response: {quote}")
                return None
        except Exception as e:
            log.error(f"Failed to fetch SPX price: {e}")
            return None

    def get_price(self, symbol: str) -> Optional[float]:
        """
        Fetch price for any symbol.

        Args:
            symbol: Stock/futures symbol

        Returns:
            Current price or None if fetch fails
        """
        try:
            quote = self.finnhub.quote(symbol)
            if quote and "c" in quote:
                price = quote["c"]
                log.debug(f"{symbol} price: {price:.2f}")
                return price
            else:
                log.warning(f"Invalid {symbol} quote response: {quote}")
                return None
        except Exception as e:
            log.error(f"Failed to fetch {symbol} price: {e}")
            return None
