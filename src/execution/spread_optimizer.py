"""Spread Optimizer — dynamically computes optimal limit order offset.
v0.3: Replaces hardcoded "bid/ask at spread → market after 3s" with
L2 order-book-aware spread targeting per coin.

Key insight: high-liquidity coins (BTC/ETH) can use tight 0.01% spreads
because there's always a counterparty. Low-liquidity coins (SEI/PEPE) need
wider spreads or the order will sit unfilled indefinitely.

The optimizer learns from fill rates over time via DuckDB — if limit orders
fill < 60% of the time, it auto-widens the spread for that coin.
"""

import numpy as np
from collections import deque
from loguru import logger


class SpreadOptimizer:
    # Default spread targets (percentage of price)
    DEFAULT_SPREAD_BPS = {
        "BTC/USDT": 0.01,  # 1 bps — tightest
        "ETH/USDT": 0.01,
        "SOL/USDT": 0.02,
        "BNB/USDT": 0.02,
        "XRP/USDT": 0.03,
        "DOGE/USDT": 0.04,
        "ADA/USDT": 0.04,
        "AVAX/USDT": 0.04,
        "DOT/USDT": 0.04,
        "ARB/USDT": 0.05,
        "OP/USDT": 0.05,
        "SUI/USDT": 0.05,
        "FET/USDT": 0.05,
        "RENDER/USDT": 0.06,
        "TIA/USDT": 0.06,
        "SEI/USDT": 0.07,
        "PEPE/USDT": 0.08,
    }

    MIN_FILL_RATE = 0.60   # below this → widen spread
    MAX_FILL_RATE = 0.90   # above this → can tighten spread
    SPREAD_STEP = 0.005    # 0.5 bps step per adjustment
    MIN_SPREAD = 0.005     # absolute floor: 0.5 bps
    MAX_SPREAD = 0.20      # absolute ceiling: 20 bps

    def __init__(self, store=None):
        self.store = store
        self._active_spreads: dict[str, float] = dict(self.DEFAULT_SPREAD_BPS)
        self._fill_history: dict[str, deque] = {}
        self._book_cache: dict[str, dict] = {}
        self._adjustment_log: list[dict] = []

    def get_optimal_offset(self, exchange, symbol: str, side: str) -> float:
        """Return the optimal limit order offset as a fraction of price.

        For BUY orders: offset BELOW current price (we want to buy cheaper)
        For SELL orders: offset ABOVE current price (we want to sell higher)
        """
        base_spread = self._active_spreads.get(symbol, 0.05) / 100
        book_data = self._fetch_book(exchange, symbol)

        if book_data:
            bid_depth = book_data.get("bid_depth", 0)
            ask_depth = book_data.get("ask_depth", 0)
            depth = bid_depth if side == "buy" else ask_depth

            if depth > 0:
                depth_factor = max(0.5, min(2.0, 100000 / (depth + 1)))
                base_spread *= depth_factor

        return round(base_spread, 6)

    def get_limit_price(self, exchange, symbol: str, side: str) -> tuple[float, float]:
        """Compute optimal limit price for a maker order.

        Returns (limit_price, offset_pct).
        """
        ticker = None
        try:
            ticker = exchange.fetch_ticker(symbol)
        except Exception:
            pass

        if not ticker:
            logger.warning(f"No ticker for {symbol} — using market order")
            return 0.0, 0.0

        offset_pct = self.get_optimal_offset(exchange, symbol, side)

        if side == "buy":
            reference = ticker.get("bid") or ticker.get("last", 0)
            limit_price = reference * (1 - offset_pct)
        else:
            reference = ticker.get("ask") or ticker.get("last", 0)
            limit_price = reference * (1 + offset_pct)

        if limit_price <= 0:
            return 0.0, 0.0

        return round(limit_price, 8), offset_pct

    def record_fill(self, symbol: str, was_filled: bool, fill_time_s: float = 0):
        """Record whether a limit order was filled. Used for adaptive spread.

        If fill rates drop below 60%, the spread auto-widens.
        If fill rates are above 90%, spreads can tighten.
        """
        if symbol not in self._fill_history:
            self._fill_history[symbol] = deque(maxlen=50)
        self._fill_history[symbol].append(int(was_filled))

        if len(self._fill_history[symbol]) < 10:
            return  # need enough samples

        self._maybe_adjust_spread(symbol)

        if self.store:
            try:
                self.store.conn.execute(
                    """INSERT OR REPLACE INTO spread_log (symbol, timestamp, spread_bps, fill_rate, was_filled)
                       VALUES (?, ?, ?, ?, ?)""",
                    [symbol, int(fill_time_s * 1000) if fill_time_s else 0,
                     round(self._active_spreads.get(symbol, 0.05), 4),
                     round(self._get_fill_rate(symbol), 2), int(was_filled)],
                )
            except Exception:
                pass

    def _get_fill_rate(self, symbol: str) -> float:
        history = self._fill_history.get(symbol, deque())
        if len(history) < 10:
            return 1.0
        return sum(history) / len(history)

    def _maybe_adjust_spread(self, symbol: str):
        fill_rate = self._get_fill_rate(symbol)
        current = self._active_spreads.get(symbol, self.DEFAULT_SPREAD_BPS.get(symbol, 0.05))

        if fill_rate < self.MIN_FILL_RATE and current < self.MAX_SPREAD:
            new_spread = min(self.MAX_SPREAD, current + self.SPREAD_STEP)
            self._active_spreads[symbol] = new_spread
            self._adjustment_log.append({
                "symbol": symbol, "old_bps": round(current, 4), "new_bps": round(new_spread, 4),
                "fill_rate": round(fill_rate, 2), "reason": "fill_rate_too_low",
            })
            logger.info(f"Spread widened: {symbol} {current:.4f}→{new_spread:.4f} bps (fill={fill_rate:.0%})")

        elif fill_rate > self.MAX_FILL_RATE and current > self.MIN_SPREAD:
            new_spread = max(self.MIN_SPREAD, current - self.SPREAD_STEP)
            self._active_spreads[symbol] = new_spread
            self._adjustment_log.append({
                "symbol": symbol, "old_bps": round(current, 4), "new_bps": round(new_spread, 4),
                "fill_rate": round(fill_rate, 2), "reason": "fill_rate_too_high",
            })
            logger.info(f"Spread tightened: {symbol} {current:.4f}→{new_spread:.4f} bps (fill={fill_rate:.0%})")

    def _fetch_book(self, exchange, symbol: str) -> dict | None:
        key = f"{symbol}_{int(__import__('time').time() // 60)}"
        cached = self._book_cache.get(key)
        if cached:
            return cached

        try:
            book = exchange.api.fetch_order_book(symbol, limit=50)
            bids = book.get("bids", [])
            asks = book.get("asks", [])
            bid_volume = sum(b[1] for b in bids[:10] if len(b) >= 2)
            ask_volume = sum(a[1] for a in asks[:10] if len(a) >= 2)
            bid_price = bids[0][0] if bids else 0
            ask_price = asks[0][0] if asks else 0
            spread = (ask_price - bid_price) / bid_price if bid_price > 0 else 0

            data = {
                "bid_price": bid_price,
                "ask_price": ask_price,
                "spread": spread,
                "bid_depth": bid_volume,
                "ask_depth": ask_volume,
                "book_imbalance": (bid_volume - ask_volume) / (bid_volume + ask_volume + 1),
            }
            self._book_cache = {key: data}
            return data
        except Exception as e:
            logger.debug(f"Order book {symbol} failed: {e}")
        return None

    def get_status(self) -> dict:
        return {
            "active_spreads_bps": {s: round(v, 4) for s, v in self._active_spreads.items()},
            "adjustments": self._adjustment_log[-20:],
            "coins_tracked": len(self._fill_history),
        }
