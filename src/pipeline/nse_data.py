"""NSE Equity Data Pipeline — Yahoo Finance integration for Indian stocks.

v1.0: NSE 50 (Nifty 50) stock data via yfinance (free, no API key).
Stores OHLCV in DuckDB `nse_candles` table (same schema as crypto candles).

Handles:
  - NSE market hours (9:15 AM - 3:30 PM IST, Mon-Fri)
  - Auto-fetch on first run, incremental thereafter
  - 10 Nifty 50 stocks pre-configured
  - INR-based portfolio tracking separate from crypto
"""

import time as time_mod
from datetime import datetime, timedelta
from pathlib import Path
import yaml
from loguru import logger

DEFAULT_NSE_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "ITC.NS", "BHARTIARTL.NS", "SBIN.NS", "LT.NS", "HCLTECH.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "SUNPHARMA.NS", "MARUTI.NS", "TITAN.NS",
]


class NSEFetcher:
    def __init__(self, store, symbols: list[str] | None = None):
        self.store = store
        self.symbols = symbols or DEFAULT_NSE_SYMBOLS
        self._ensure_table()

    def _ensure_table(self):
        self.store.conn.execute("""
            CREATE TABLE IF NOT EXISTS nse_candles (
                symbol VARCHAR,
                timeframe VARCHAR,
                timestamp BIGINT,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                PRIMARY KEY (symbol, timeframe, timestamp)
            )
        """)

    def fetch_historical(self, days_back: int = 365, symbols: list[str] | None = None):
        """Download historical OHLCV for NSE stocks via yfinance."""
        try:
            import yfinance as yf
        except ImportError:
            logger.error("yfinance not installed. Run: pip install yfinance")
            return {}

        syms = symbols or self.symbols
        results = {}

        for sym in syms[:10]:
            try:
                ticker = yf.Ticker(sym)
                end = datetime.now()
                start = end - timedelta(days=days_back)
                df = ticker.history(start=start, end=end, interval="1d")

                if df.empty:
                    logger.debug(f"NSE {sym}: no data")
                    results[sym] = 0
                    continue

                count = 0
                for idx, row in df.iterrows():
                    ts = int(idx.timestamp() * 1000)
                    exists = self.store.conn.execute(
                        "SELECT 1 FROM nse_candles WHERE symbol=? AND timeframe='1d' AND timestamp=?",
                        [sym, ts],
                    ).fetchone()
                    if exists:
                        continue
                    self.store.conn.execute(
                        """INSERT INTO nse_candles VALUES (?, '1d', ?, ?, ?, ?, ?, ?)""",
                        [sym, ts, float(row["Open"]), float(row["High"]),
                         float(row["Low"]), float(row["Close"]), float(row["Volume"])],
                    )
                    count += 1

                results[sym] = count
                logger.info(f"NSE {sym}: {count} candles")
                time_mod.sleep(0.5)

            except Exception as e:
                logger.debug(f"NSE {sym} failed: {e}")
                results[sym] = 0

        total = sum(results.values())
        logger.success(f"NSE: fetched {total} candles across {len(syms)} stocks")
        return results

    def get_candles(self, symbol: str, limit: int = 100) -> list[dict]:
        """Retrieve stored NSE candles for a symbol."""
        rows = self.store.conn.execute(
            "SELECT * FROM nse_candles WHERE symbol=? ORDER BY timestamp DESC LIMIT ?",
            [symbol, limit],
        ).fetchdf()
        return rows.to_dict("records") if len(rows) > 0 else []

    def is_market_open(self) -> bool:
        """Check if NSE is currently open for trading."""
        now = datetime.now()
        if now.weekday() >= 5:  # Saturday/Sunday
            return False
        market_open = now.replace(hour=9, minute=15, second=0)
        market_close = now.replace(hour=15, minute=30, second=0)
        return market_open <= now <= market_close

    def minutes_to_open(self) -> int:
        """Minutes until NSE opens. Returns 0 if already open."""
        now = datetime.now()
        if now.weekday() >= 5:
            return -1
        market_open = now.replace(hour=9, minute=15, second=0)
        if now >= market_open and now <= now.replace(hour=15, minute=30):
            return 0
        if now < market_open:
            return int((market_open - now).total_seconds() / 60)
        return -1
