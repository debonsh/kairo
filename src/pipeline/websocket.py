"""Real-time WebSocket data stream via ccxt.pro.

Wire-in (P0.2): every incoming OHLCV batch is also folded into
information-driven bars (volume bars by default) via ``info_bars.py`` and
persisted to the ``info_bars`` table. Live signal generation can then read
info-bar data instead of pure time-based OHLCV.
"""

import asyncio
from datetime import datetime
from loguru import logger
from .store import MarketStore
from .info_bars import candles_to_info_bars


class LiveStream:
    def __init__(self, store: MarketStore, exchange_id: str = "bybit",
                 info_bar_type: str = "volume", info_bars_enabled: bool = True):
        self.store = store
        self.exchange_id = exchange_id
        self.info_bar_type = info_bar_type
        self.info_bars_enabled = info_bars_enabled
        self.exchange = None
        self.running = False
        self._task = None

    async def start(self, symbols: list[str], timeframes: list[str] | None = None):
        import ccxt.pro as ccxtpro

        ex_class = getattr(ccxtpro, self.exchange_id)
        self.exchange = ex_class({"enableRateLimit": True})
        self.running = True

        tasks = []
        for symbol in symbols:
            tasks.append(self._watch_ticker(symbol))
            if timeframes:
                for tf in timeframes:
                    tasks.append(self._watch_ohlcv(symbol, tf))

        logger.info(f"LiveStream: watching {len(symbols)} symbols on {self.exchange_id}")
        await asyncio.gather(*tasks)

    async def _watch_ticker(self, symbol: str):
        while self.running:
            try:
                ticker = await self.exchange.watch_ticker(symbol)
                ticker["symbol"] = symbol
                ticker["timestamp"] = int(datetime.now().timestamp() * 1000)
                self.store.insert_ticker(self.exchange_id, ticker)
            except Exception as e:
                logger.warning(f"Ticker stream error for {symbol}: {e}")
                await asyncio.sleep(5)

    async def _watch_ohlcv(self, symbol: str, timeframe: str):
        while self.running:
            try:
                candles = await self.exchange.watch_ohlcv(symbol, timeframe)
                self.store.insert_candles(self.exchange_id, symbol, timeframe, candles)

                # P0.2: fold live candles into info bars and persist them, so
                # the info-bar view is always current for signal generation.
                if self.info_bars_enabled and timeframe == "15m":
                    try:
                        info = candles_to_info_bars(candles, bar_type=self.info_bar_type)
                        self.store.insert_info_bars(self.exchange_id, symbol, self.info_bar_type, info)
                    except Exception as e:
                        logger.debug(f"Info bars {symbol} skip: {e}")

                latest = candles[-1] if candles else None
                if latest:
                    logger.debug(f"OHLCV {symbol} {timeframe}: close={latest[4]}")
            except Exception as e:
                logger.warning(f"OHLCV stream error for {symbol}:{timeframe}: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        self.running = False
        if self.exchange:
            await self.exchange.close()
        logger.info("LiveStream stopped")
