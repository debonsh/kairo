"""Derivatives context — funding rates + open interest from perpetual markets.

The 5-strategy ensemble is blind to leverage and positioning. Funding rate
extremes reveal crowded trades (liquidation fuel); OI changes reveal whether a
breakout is backed by new money or is a weak short-covering rally. Both are
free public REST data.

Perpetual data is fetched from Bybit mainnet regardless of the spot/testnet
trading mode — derivatives are listed there and the endpoints are public.
"""

import time
import ccxt
from loguru import logger


class DerivativesAgent:
    def __init__(self, crowd_threshold_pct: float = 30.0, cache_seconds: int = 300):
        self.crowd_threshold = crowd_threshold_pct  # annualized funding %, per side
        self.cache_seconds = cache_seconds
        self._client: ccxt.Exchange | None = None
        self._cache: dict[str, dict] = {}
        self._last_oi: dict[str, float] = {}

    def _get_client(self) -> ccxt.Exchange:
        if self._client is None:
            self._client = ccxt.bybit({"enableRateLimit": True})
        return self._client

    def get_context(self, symbol: str) -> dict:
        """Funding + OI context for a spot symbol (BTC/USDT → perp BTC/USDT:USDT).

        Returns a neutral dict on failure so the pipeline never crashes on it.
        """
        now = time.time()
        cached = self._cache.get(symbol)
        if cached and now - cached["ts"] < self.cache_seconds:
            return cached["data"]

        ctx = {
            "symbol": symbol,
            "source": "derivatives",
            "ok": False,
            "funding_rate": None,
            "funding_annualized_pct": None,
            "crowded_long": False,
            "crowded_short": False,
            "oi_delta_pct": None,
            "oi_rising": None,
        }
        try:
            perp = f"{symbol}:USDT"
            client = self._get_client()
            funding = client.fetch_funding_rate(perp)
            oi = client.fetch_open_interest(perp)

            funding_rate = float(funding.get("fundingRate") or 0)
            annualized = funding_rate * 3 * 365 * 100  # per-8h → annualized %

            oi_amount = float(oi.get("openInterestAmount")
                              or oi.get("openInterestValue") or 0)
            prev_oi = self._last_oi.get(symbol)
            oi_delta = None
            if prev_oi and prev_oi > 0 and oi_amount > 0:
                oi_delta = (oi_amount - prev_oi) / prev_oi * 100
            if oi_amount > 0:
                self._last_oi[symbol] = oi_amount

            ctx.update({
                "ok": True,
                "funding_rate": round(funding_rate, 8),
                "funding_annualized_pct": round(annualized, 2),
                "crowded_long": annualized > self.crowd_threshold,
                "crowded_short": annualized < -self.crowd_threshold,
                "oi_delta_pct": round(oi_delta, 2) if oi_delta is not None else None,
                "oi_rising": oi_delta is not None and oi_delta > 0,
            })
        except Exception as e:
            logger.debug(f"Derivatives {symbol} skipped: {e}")

        self._cache[symbol] = {"ts": now, "data": ctx}
        return ctx
