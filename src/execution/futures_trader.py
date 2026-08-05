"""Futures Trader — perpetual futures execution layer for USDT-M contracts.

Extends the existing execution pipeline with:
- USDT-M perpetual contract support on Bybit
- Configurable leverage (1x-2x, gated by FuturesGate)
- Isolated margin mode (positions don't share collateral)
- Real-time liquidation distance checks before order placement
- Automatic leverage scaling on mode switches (vanilla → 1x, aggressive → up to 2x)

Liquidation formula for isolated linear perps:
  liq_distance_pct = (entry - liq_price) / entry * leverage * 100   (for longs)
  liq_distance_pct = (liq_price - entry) / entry * leverage * 100   (for shorts)
"""

import os
import time as time_mod
import ccxt
from loguru import logger


class FuturesTrader:
    MIN_LIQ_DISTANCE_PCT = 5.0   # reject order if liquidation < 5% away
    MAX_LEVERAGE = 2.0
    MIN_LEVERAGE = 1.0

    def __init__(self, exchange_id: str = "bybit", testnet: bool = True, leverage: float = 1.0):
        self.exchange_id = exchange_id
        self.testnet = testnet
        self.leverage = max(self.MIN_LEVERAGE, min(leverage, self.MAX_LEVERAGE))
        self.api = self._create_client()
        self._margin_mode_set: set[str] = set()

    def _create_client(self) -> ccxt.Exchange:
        ex_class = getattr(ccxt, self.exchange_id)
        config = {
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        }

        if self.testnet:
            if self.exchange_id == "bybit":
                config["urls"] = {"api": {
                    "public": "https://api-testnet.bybit.com",
                    "private": "https://api-testnet.bybit.com",
                }}

        if not self.testnet:
            key = os.getenv(f"{self.exchange_id.upper()}_API_KEY", "")
            secret = os.getenv(f"{self.exchange_id.upper()}_API_SECRET", "")
            if key and secret:
                config["apiKey"] = key
                config["secret"] = secret

        logger.info(f"Futures: {self.exchange_id} {'[TESTNET]' if self.testnet else '[LIVE]'} "
                    f"| leverage: {self.leverage}x | margin: isolated")
        return ex_class(config)

    def set_leverage(self, leverage: float, symbol: str):
        """Set leverage for a symbol pair. Clamped to [1, MAX_LEVERAGE].

        Must be called before opening a position on a new symbol.
        In isolated margin, leverage affects the margin required per position.
        """
        self.leverage = max(self.MIN_LEVERAGE, min(leverage, self.MAX_LEVERAGE))
        try:
            self._ensure_isolated(symbol)
            self.api.set_leverage(int(self.leverage), self._perp_symbol(symbol))
            logger.info(f"Leverage set: {symbol} → {int(self.leverage)}x")
        except Exception as e:
            logger.warning(f"set_leverage {symbol} failed: {e}")

    def _ensure_isolated(self, symbol: str):
        """Set isolated margin mode for a symbol. Idempotent."""
        perp = self._perp_symbol(symbol)
        if perp in self._margin_mode_set:
            return
        try:
            self.api.set_margin_mode("isolated", perp)
            self._margin_mode_set.add(perp)
        except Exception as e:
            err = str(e).lower()
            if "same mode" in err or "already" in err:
                self._margin_mode_set.add(perp)
                return
            logger.warning(f"set_margin_mode {symbol} failed: {e}")

    def check_liquidation_distance(self, symbol: str, side: str, entry_price: float) -> dict:
        """Check how close entry is to estimated liquidation price.

        Calls exchange to get real-time liquidation distance info for open positions.
        For a NEW position (not yet opened), we estimate using the liquidation price
        formula: isolated perp liquidation ≈ entry * (1 - 1/leverage + mmr) for longs.

        Returns dict with {safe: bool, estimated_liq_pct: float, reason: str}
        """
        try:
            perp = self._perp_symbol(symbol)
            positions = self.api.fetch_positions([perp])

            existing_liq_pcts = []
            for pos in positions:
                if pos.get("symbol") == perp and float(pos.get("contracts") or 0) > 0:
                    liq_price = float(pos.get("liquidationPrice") or 0)
                    mark = float(pos.get("markPrice") or entry_price)
                    if liq_price > 0 and mark > 0:
                        pos_side = pos.get("side", side).lower()
                        if pos_side in ("long", "buy"):
                            distance_pct = (mark - liq_price) / mark * 100
                        else:
                            distance_pct = (liq_price - mark) / mark * 100
                        existing_liq_pcts.append(distance_pct)

            mmr = 0.005
            if side.lower() in ("long", "buy"):
                est_liq = entry_price * (1 - 1 / self.leverage + mmr)
                distance_pct = max(0, (entry_price - est_liq) / entry_price * 100)
            else:
                est_liq = entry_price * (1 + 1 / self.leverage - mmr)
                distance_pct = max(0, (est_liq - entry_price) / entry_price * 100)

            is_safe = distance_pct >= self.MIN_LIQ_DISTANCE_PCT

            return {
                "safe": is_safe,
                "estimated_liq_pct": round(distance_pct, 2),
                "existing_liq_pcts": [round(p, 2) for p in existing_liq_pcts],
                "leverage": self.leverage,
                "reason": "ok" if is_safe else
                    f"Liquidation too close: {distance_pct:.1f}% < {self.MIN_LIQ_DISTANCE_PCT}% minimum",
            }
        except Exception as e:
            logger.warning(f"liq_distance {symbol} failed: {e}")
            return {"safe": False, "estimated_liq_pct": 0.0, "existing_liq_pcts": [],
                    "leverage": self.leverage, "reason": f"API error: {e}"}

    def open_position(self, symbol: str, side: str, amount: float,
                      stop_loss: float | None = None, take_profit: float | None = None) -> dict | None:
        """Open a perpetual futures position.

        Args:
            symbol: spot-style symbol, e.g. 'BTC/USDT' (auto-converted to 'BTC/USDT:USDT')
            side: 'buy' (long) or 'sell' (short)
            amount: contract quantity in base asset units
            stop_loss: optional SL price (uses exchange stop-loss order)
            take_profit: optional TP price (uses exchange take-profit order)
        """
        perp = self._perp_symbol(symbol)

        self._ensure_isolated(symbol)
        self.set_leverage(self.leverage, symbol)

        try:
            ticker = self.api.fetch_ticker(perp)
            entry_price = ticker.get("last", ticker.get("close", 0))
        except Exception:
            entry_price = 0

        if entry_price <= 0:
            logger.warning(f"No price for {perp} — cannot open position")
            return None

        liq_check = self.check_liquidation_distance(symbol, side.lower(), entry_price)
        if not liq_check["safe"]:
            logger.warning(f"Liquidation check failed for {symbol}: {liq_check['reason']}")
            return None

        params = {}
        position_side = "LONG" if side.lower() in ("long", "buy") else "SHORT"

        if stop_loss is not None:
            params["stopLoss"] = {"stop_loss": str(stop_loss), "sl_trigger_by": "markPrice"}
        if take_profit is not None:
            params["takeProfit"] = {"take_profit": str(take_profit), "tp_trigger_by": "markPrice"}

        try:
            if self.testnet:
                logger.info(f"[PAPER-FUTURES] {position_side} {symbol} x {amount:.4f} "
                           f"@ ~{entry_price:.2f} | leverage: {self.leverage}x")
                return {
                    "id": f"paper_futures_{position_side}_{int(time_mod.time())}",
                    "symbol": symbol,
                    "perp_symbol": perp,
                    "side": side,
                    "entry_price": entry_price,
                    "amount": amount,
                    "leverage": self.leverage,
                    "status": "paper",
                    "mode": "futures",
                }

            order = self.api.create_order(
                symbol=perp,
                type="market",
                side=side,
                amount=amount,
                params=params,
            )

            logger.info(f"[FUTURES] {position_side} {symbol} x {amount:.4f} "
                       f"@ ~{entry_price:.2f} | {self.leverage}x | id={order.get('id', '?')}")

            return {
                "id": order.get("id", ""),
                "symbol": symbol,
                "perp_symbol": perp,
                "side": side,
                "entry_price": order.get("price") or entry_price,
                "amount": amount,
                "leverage": self.leverage,
                "status": order.get("status", "open"),
                "mode": "futures",
                "exchange_response": order,
            }
        except Exception as e:
            logger.error(f"Futures order {side} {symbol} failed: {e}")
            return None

    def close_position(self, symbol: str, side: str | None = None) -> dict | None:
        """Close an open futures position. If side is None, auto-detects and reverses."""
        perp = self._perp_symbol(symbol)

        try:
            positions = self.api.fetch_positions([perp])
            open_pos = None
            for p in positions:
                if float(p.get("contracts") or 0) > 0:
                    open_pos = p
                    break

            if not open_pos:
                logger.debug(f"No open futures position for {symbol}")
                return None

            pos_side = side or ("sell" if open_pos.get("side", "").lower() == "long" else "buy")
            contracts = float(open_pos.get("contracts", 0))

            if self.testnet:
                logger.info(f"[PAPER-FUTURES] CLOSE {symbol} | contracts: {contracts}")
                return {"id": f"paper_close_{int(time_mod.time())}", "status": "paper", "mode": "futures"}

            order = self.api.create_order(
                symbol=perp, type="market", side=pos_side,
                amount=contracts, params={"reduceOnly": True},
            )
            logger.info(f"[FUTURES] Closed {symbol} | id={order.get('id', '?')}")
            return {"id": order.get("id", ""), "symbol": symbol, "status": "closed", "mode": "futures"}
        except Exception as e:
            logger.error(f"Futures close {symbol} failed: {e}")
            return None

    def fetch_positions(self, symbol: str | None = None) -> list[dict]:
        """Fetch current open futures positions with liquidation prices."""
        try:
            kwargs = {}
            if symbol:
                kwargs["symbols"] = [self._perp_symbol(symbol)]
            return self.api.fetch_positions(**kwargs)
        except Exception as e:
            logger.warning(f"fetch_positions failed: {e}")
            return []

    def get_liquidation_heat(self) -> dict[str, float]:
        """Return liquidation distance % for all open positions. Sorted by risk."""
        heat = {}
        try:
            for pos in self.fetch_positions():
                liq_price = float(pos.get("liquidationPrice") or 0)
                mark = float(pos.get("markPrice") or 0)
                entry = float(pos.get("entryPrice") or 0)
                if liq_price <= 0 or mark <= 0:
                    continue
                sym = str(pos.get("symbol", "?")).split(":")[0]
                side = pos.get("side", "long").lower()
                if side in ("long", "buy") and liq_price < mark:
                    distance_pct = (mark - liq_price) / mark * 100
                elif side in ("short", "sell") and liq_price > mark:
                    distance_pct = (liq_price - mark) / mark * 100
                else:
                    distance_pct = 0.0
                heat[sym] = round(distance_pct, 2)
        except Exception:
            pass
        return dict(sorted(heat.items(), key=lambda x: x[1]))

    @staticmethod
    def _perp_symbol(spot_symbol: str) -> str:
        """Convert 'BTC/USDT' → 'BTC/USDT:USDT' (USDT-M perpetual)."""
        if ":" in spot_symbol:
            return spot_symbol
        return f"{spot_symbol}:USDT"

    def get_status(self) -> dict:
        return {
            "exchange": self.exchange_id,
            "testnet": self.testnet,
            "leverage": self.leverage,
            "margin_mode": "isolated",
            "liquidation_heat": self.get_liquidation_heat(),
        }
