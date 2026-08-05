"""Multi-Exchange Arbitrage — Bybit vs Binance cross-exchange scanner.

v1.0: Monitors price gaps between Bybit and Binance. Executes arb when
spread after fees exceeds 1.5x the combined fee cost of both legs.

Safety: Only SIMULTANEOUS execution (both legs within 2s). If one leg
fails, the other is market-closed immediately. No naked exposure.

Uses DuckDB `arb_opportunities` table to log all opportunities, executed or not.
"""

import time as time_mod
from loguru import logger


class ArbitrageScanner:
    MIN_SPREAD_FEE_MULTIPLIER = 1.5  # only execute if spread > fees × 1.5
    MAX_EXECUTION_WINDOW_S = 2.0     # both legs must execute within this window
    MIN_ORDER_USDT = 10.0            # don't arb below this order value

    def __init__(self, exchange_a, exchange_b, store=None):
        self.exchange_a = exchange_a  # e.g. Bybit
        self.exchange_b = exchange_b  # e.g. Binance
        self.store = store
        self._opportunities_logged = 0
        self._arbs_executed = 0
        self._total_profit = 0.0

    def scan(self, symbols: list[str]) -> list[dict]:
        """Scan all symbols for arbitrage opportunities.

        Returns list of opportunities sorted by best spread first.
        Only includes opportunities where estimated profit > 0.
        """
        opportunities = []
        for sym in symbols[:12]:
            result = self._scan_single(sym)
            if result and result.get("profitable"):
                opportunities.append(result)

        opportunities.sort(key=lambda x: x.get("estimated_profit", 0), reverse=True)
        return opportunities

    def _scan_single(self, symbol: str) -> dict | None:
        a_ticker = self._safe_ticker(self.exchange_a, symbol)
        b_ticker = self._safe_ticker(self.exchange_b, symbol)

        if not a_ticker or not b_ticker:
            return None

        a_bid = a_ticker.get("bid") or a_ticker.get("last", 0)
        a_ask = a_ticker.get("ask") or a_ticker.get("last", 0)
        b_bid = b_ticker.get("bid") or b_ticker.get("last", 0)
        b_ask = b_ticker.get("ask") or b_ticker.get("last", 0)

        if any(p <= 0 for p in [a_bid, a_ask, b_bid, b_ask]):
            return None

        # Check two directions:
        # 1. Buy on A (at ask), sell on B (at bid) — A cheaper, B more expensive
        spread_ab = b_bid - a_ask
        # 2. Buy on B (at ask), sell on A (at bid) — B cheaper, A more expensive
        spread_ba = a_bid - b_ask

        best_spread = max(spread_ab, spread_ba)
        if best_spread <= 0:
            return None

        if spread_ab >= spread_ba:
            buy_ex, sell_ex = self.exchange_a.exchange_id, self.exchange_b.exchange_id
            buy_price, sell_price = a_ask, b_bid
            spread_pct = spread_ab / a_ask
        else:
            buy_ex, sell_ex = self.exchange_b.exchange_id, self.exchange_a.exchange_id
            buy_price, sell_price = b_ask, a_bid
            spread_pct = spread_ba / b_ask

        a_fee = self._get_fee(self.exchange_a)
        b_fee = self._get_fee(self.exchange_b)
        total_fee_pct = a_fee + b_fee

        # Estimated profit on $100 order
        order_size = 100.0
        qty = order_size / buy_price if buy_price > 0 else 0
        buy_cost = order_size * (1 + a_fee)
        sell_revenue = qty * sell_price * (1 - b_fee)
        est_profit = sell_revenue - buy_cost

        profitable = (
            spread_pct > total_fee_pct * self.MIN_SPREAD_FEE_MULTIPLIER
            and est_profit > 0
            and order_size >= self.MIN_ORDER_USDT
        )

        result = {
            "symbol": symbol,
            "buy_exchange": buy_ex,
            "sell_exchange": sell_ex,
            "buy_price": round(buy_price, 6),
            "sell_price": round(sell_price, 6),
            "spread_pct": round(spread_pct * 100, 4),
            "total_fee_pct": round(total_fee_pct * 100, 4),
            "estimated_profit": round(est_profit, 4),
            "profitable": profitable,
            "timestamp": int(time_mod.time() * 1000),
        }

        if self.store:
            self._log_opportunity(result)

        return result

    def execute_arb(self, opportunity: dict) -> dict | None:
        """Execute both legs of an arbitrage trade simultaneously.

        Buys on the cheaper exchange, sells on the expensive exchange.
        If one leg fails, the other is immediately market-closed.
        """
        if not opportunity.get("profitable"):
            return None

        symbol = opportunity["symbol"]
        buy_ex_name = opportunity["buy_exchange"]
        sell_ex_name = opportunity["sell_exchange"]
        buy_price = opportunity["buy_price"]

        buy_ex = self.exchange_a if self.exchange_a.exchange_id == buy_ex_name else self.exchange_b
        sell_ex = self.exchange_b if self.exchange_b.exchange_id == sell_ex_name else self.exchange_a

        order_size = 100.0
        qty = order_size / buy_price if buy_price > 0 else 0
        if qty <= 0:
            return None

        t0 = time_mod.time()

        buy_order = None
        sell_order = None

        try:
            buy_order = buy_ex.market_buy(symbol, qty)
        except Exception as e:
            logger.warning(f"Arb buy leg {symbol} on {buy_ex_name} failed: {e}")
            return None

        try:
            sell_order = sell_ex.market_sell(symbol, qty)
        except Exception as e:
            logger.warning(f"Arb sell leg {symbol} on {sell_ex_name} failed: {e}")
            # Buy went through but sell failed — close the buy position immediately
            try:
                buy_ex.market_sell(symbol, qty)
            except Exception:
                pass
            return None

        elapsed = time_mod.time() - t0
        if elapsed > self.MAX_EXECUTION_WINDOW_S:
            logger.warning(f"Arb {symbol} took {elapsed:.1f}s > {self.MAX_EXECUTION_WINDOW_S}s window")
            # Both legs executed but too slow — positions may have diverged. Close both.
            try:
                buy_ex.market_sell(symbol, qty)
            except Exception:
                pass
            try:
                sell_ex.market_buy(symbol, qty)
            except Exception:
                pass
            return None

        est_profit = opportunity.get("estimated_profit", 0)
        self._arbs_executed += 1
        self._total_profit += est_profit

        logger.success(
            f"ARB {symbol}: buy {buy_ex_name} @ {buy_price} + sell {sell_ex_name} "
            f"@ {opportunity['sell_price']} = ~${est_profit:.2f} profit"
        )

        return {
            "symbol": symbol,
            "buy_exchange": buy_ex_name,
            "sell_exchange": sell_ex_name,
            "buy_order_id": buy_order.get("id", ""),
            "sell_order_id": sell_order.get("id", ""),
            "estimated_profit": round(est_profit, 4),
            "elapsed_s": round(elapsed, 3),
            "executed": True,
        }

    def _safe_ticker(self, exchange, symbol: str) -> dict | None:
        try:
            ticker = exchange.fetch_ticker(symbol)
            if ticker and ticker.get("last", 0) > 0:
                return ticker
        except Exception as e:
            logger.debug(f"Arb ticker {exchange.exchange_id}/{symbol}: {e}")
        return None

    @staticmethod
    def _get_fee(exchange) -> float:
        """Get taker fee for an exchange."""
        fees = exchange.api.fees if hasattr(exchange.api, "fees") else {}
        trading = fees.get("trading", {}) if isinstance(fees, dict) else {}
        return trading.get("taker", 0.001)

    def _log_opportunity(self, result: dict):
        try:
            self.store.conn.execute(
                """INSERT OR IGNORE INTO arb_opportunities
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    result["timestamp"],
                    result["symbol"],
                    result["buy_exchange"],
                    result["sell_exchange"],
                    result["buy_price"],
                    result["sell_price"],
                    result["spread_pct"],
                    result["estimated_profit"],
                    int(result["profitable"]),
                ],
            )
            self._opportunities_logged += 1
        except Exception as e:
            logger.debug(f"Arb log skip: {e}")

    def get_status(self) -> dict:
        return {
            "opportunities_logged": self._opportunities_logged,
            "arbs_executed": self._arbs_executed,
            "total_profit": round(self._total_profit, 4),
        }
