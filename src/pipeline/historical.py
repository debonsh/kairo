"""Historical OHLCV data downloader via ccxt."""

import ccxt
import time
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
import yaml

from .store import MarketStore


class HistoricalFetcher:
    TIMEFRAME_MS = {
        "1m": 60_000,
        "5m": 300_000,
        "15m": 900_000,
        "1h": 3_600_000,
        "4h": 14_400_000,
        "1d": 86_400_000,
        "1w": 604_800_000,
    }

    def __init__(self, store: MarketStore, exchanges: list[str] | None = None):
        self.store = store
        self.exchanges = {}
        exchange_ids = exchanges or ["bybit", "binance"]
        for ex_id in exchange_ids:
            try:
                ex_class = getattr(ccxt, ex_id)
                self.exchanges[ex_id] = ex_class({"enableRateLimit": True})
                logger.info(f"Initialized {ex_id}")
            except AttributeError:
                logger.warning(f"Exchange {ex_id} not found in ccxt")

    def fetch_historical(
        self,
        symbols: list[str],
        timeframes: list[str],
        days_back: int = 365,
        exchange: str | None = None,
    ) -> dict[str, int]:
        """Bulk download historical candles. Returns {exchange_symbol_tf: count}."""
        results = {}
        exchanges_to_use = (
            {exchange: self.exchanges[exchange]} if exchange and exchange in self.exchanges
            else self.exchanges
        )

        for ex_id, ex_api in exchanges_to_use.items():
            if not ex_api.has.get("fetchOHLCV", False):
                logger.warning(f"{ex_id} doesn't support fetchOHLCV")
                continue

            for symbol in symbols:
                for tf in timeframes:
                    if tf not in self.TIMEFRAME_MS:
                        logger.warning(f"Unsupported timeframe: {tf}")
                        continue

                    key = f"{ex_id}:{symbol}:{tf}"
                    try:
                        count = self._fetch_one(ex_api, ex_id, symbol, tf, days_back)
                        results[key] = count
                        logger.info(f"{key}: {count} candles downloaded")
                        time.sleep(ex_api.rateLimit / 1000)
                    except Exception as e:
                        logger.error(f"Failed {key}: {e}")
                        results[key] = 0

        return results

    def _fetch_one(self, exchange, ex_id: str, symbol: str, tf: str, days_back: int) -> int:
        since = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
        tf_ms = self.TIMEFRAME_MS[tf]
        total = 0
        limit = 1000

        while since < int(datetime.now().timestamp() * 1000):
            candles = exchange.fetch_ohlcv(symbol, tf, since=since, limit=limit)
            if not candles:
                break

            since = candles[-1][0] + tf_ms
            total += self.store.insert_candles(ex_id, symbol, tf, candles)

            if len(candles) < limit:
                break

        return total

    def fetch_recent(self, symbols: list[str], timeframes: list[str], exchange: str = "bybit") -> dict[str, int]:
        """Fetch only last 7 days — for initial setup quick start."""
        return self.fetch_historical(symbols, timeframes, days_back=7, exchange=exchange)

    def fetch_full(self, symbols: list[str], timeframes: list[str], exchange: str = "bybit") -> dict[str, int]:
        """Fetch last 365 days — full historical coverage."""
        return self.fetch_historical(symbols, timeframes, days_back=365, exchange=exchange)


def load_coins(config_path: str = "config/coins.yaml") -> list[str]:
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    return [c["symbol"] for c in cfg["coins"]]
