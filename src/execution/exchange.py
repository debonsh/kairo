"""Exchange abstraction — unified ccxt wrapper for Binance + Bybit.
Maker-first order routing (limit at spread → market fallback).
Startup security checklist + IP whitelist support."""

import os
import time
import ccxt
from loguru import logger


class Exchange:
    def __init__(self, exchange_id: str = "bybit", testnet: bool = True):
        self.exchange_id = exchange_id
        self.testnet = testnet
        self.api = self._create_client()
        self.consecutive_errors = 0
        self.total_errors = 0
        self._print_security_checklist()

    def _create_client(self):
        ex_class = getattr(ccxt, self.exchange_id)
        config = {"enableRateLimit": True}

        if self.testnet:
            if self.exchange_id == "bybit":
                config["urls"] = {"api": {"public": "https://api-testnet.bybit.com",
                                         "private": "https://api-testnet.bybit.com"}}
            elif self.exchange_id == "binance":
                config["urls"] = {"api": {"public": "https://testnet.binance.vision",
                                         "private": "https://testnet.binance.vision"}}

        if not self.testnet:
            key = os.getenv(f"{self.exchange_id.upper()}_API_KEY", "")
            secret = os.getenv(f"{self.exchange_id.upper()}_API_SECRET", "")
            if key and secret:
                config["apiKey"] = key
                config["secret"] = secret

        logger.info(f"Exchange: {self.exchange_id} {'[TESTNET]' if self.testnet else '[LIVE]'}")
        return ex_class(config)

    def _print_security_checklist(self):
        logger.warning("=" * 50)
        logger.warning("SECURITY CHECKLIST")
        logger.warning("=" * 50)
        logger.warning("[ ] API keys are trade-only (no withdrawal permission)")
        logger.warning("[ ] IP whitelist enabled on exchange")
        logger.warning("[ ] .env file is NOT committed to git")
        logger.warning("[ ] 2FA / Passkey enabled on exchange account")
        logger.warning(f"[ ] {'TESTNET' if self.testnet else 'SEPARATE account (not your main exchange)'}")

        ip_whitelist = os.getenv("API_IP_WHITELIST", "")
        if ip_whitelist:
            logger.info(f"[✓] IP whitelist configured: {ip_whitelist}")
        else:
            logger.warning("[ ] API_IP_WHITELIST not set — configure for live trading")

        logger.warning("=" * 50)

    def fetch_balance(self) -> dict:
        try:
            balance = self.api.fetch_balance()
            return {
                "total": balance.get("total", {}).get("USDT", 0),
                "free": balance.get("free", {}).get("USDT", 0),
                "used": balance.get("used", {}).get("USDT", 0),
            }
        except Exception as e:
            logger.error(f"fetch_balance failed: {e}")
            return {"total": 0, "free": 0, "used": 0}

    def fetch_ticker(self, symbol: str) -> dict | None:
        try:
            result = self.api.fetch_ticker(symbol)
            self._record_api_success()
            return result
        except Exception as e:
            self._record_api_error()
            logger.debug(f"fetch_ticker {symbol} skipped: {e}")
            return None

    def fetch_ohlcv(self, symbol: str, timeframe: str = "15m", limit: int = 100) -> list:
        try:
            result = self.api.fetch_ohlcv(symbol, timeframe, limit=limit)
            self._record_api_success()
            return result
        except Exception as e:
            self._record_api_error()
            logger.error(f"fetch_ohlcv {symbol} failed: {e}")
            return []

    def _record_api_success(self):
        self.consecutive_errors = 0

    def _record_api_error(self):
        self.consecutive_errors += 1
        self.total_errors += 1

    def api_health(self) -> dict:
        """API error circuit state — main loop auto-pauses past the threshold."""
        return {
            "consecutive_errors": self.consecutive_errors,
            "total_errors": self.total_errors,
            "healthy": self.consecutive_errors < 3,
        }

    def fetch_positions(self) -> list[dict]:
        try:
            return self.api.fetch_positions()
        except Exception as e:
            logger.warning(f"fetch_positions failed: {e}")
            return []

    def place_order(self, symbol: str, side: str, amount: float, spread_optimizer=None) -> dict:
        """Maker-first: try limit order at optimized spread. Fall back to market after 3s.

        Uses SpreadOptimizer (v0.3) when available to compute optimal limit offset
        from L2 order book. Falls back to bid/ask-at-spread if optimizer unavailable.
        """
        if self.testnet:
            logger.info(f"[PAPER] {side.upper()} {symbol} x {amount}")
            return {"id": f"paper_{side}", "symbol": symbol, "amount": amount, "status": "paper"}

        try:
            if spread_optimizer:
                limit_price, offset_pct = spread_optimizer.get_limit_price(self, symbol, side)
                if limit_price > 0 and offset_pct > 0:
                    try:
                        order = self.api.create_limit_order(symbol, side, amount, limit_price)
                        time.sleep(3)
                        updated = self.api.fetch_order(order["id"], symbol)
                        was_filled = updated.get("status") != "open"
                        spread_optimizer.record_fill(symbol, was_filled)
                        if was_filled:
                            return updated
                        self.api.cancel_order(order["id"], symbol)
                        logger.debug(f"Optimized limit {symbol} unfilled at {offset_pct*100:.2f}% offset")
                    except Exception:
                        pass

            # Fallback: bid/ask at spread
            ticker = self.api.fetch_ticker(symbol)
            maker_price = ticker.get("bid") if side == "sell" else ticker.get("ask")
            if maker_price and maker_price > 0:
                try:
                    order = self.api.create_limit_order(symbol, side, amount, maker_price)
                    time.sleep(3)
                    updated = self.api.fetch_order(order["id"], symbol)
                    if updated.get("status") == "open":
                        self.api.cancel_order(order["id"], symbol)
                        raise Exception("Limit order unfilled")
                    return updated
                except Exception:
                    pass

            # Final fallback: market order
            return self.api.create_market_order(symbol, side, amount)
        except Exception as e:
            logger.error(f"Order {side} {symbol} failed: {e}")
            raise

    def market_buy(self, symbol: str, amount: float) -> dict:
        return self.place_order(symbol, "buy", amount)

    def market_sell(self, symbol: str, amount: float) -> dict:
        return self.place_order(symbol, "sell", amount)

    def fetch_open_orders(self, symbol: str | None = None) -> list:
        try:
            return self.api.fetch_open_orders(symbol)
        except Exception:
            return []

    def cancel_all_orders(self, symbol: str | None = None):
        try:
            return self.api.cancel_all_orders(symbol)
        except Exception as e:
            logger.error(f"cancel_all_orders failed: {e}")
