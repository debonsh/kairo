"""Market Making — liquidity-provision execution path (roadmap P1.1).

Structurally different edge source from the 5 directional strategies: quote
both sides of the book and capture the spread, adjusting inventory as fills
come in. Its risk is adverse selection and inventory skew, NOT directional
exposure — so it is genuinely uncorrelated with the existing ensemble.

Integration note: this is NOT a 6th ``evaluate()`` signal that slots into the
existing ensemble. It is a separate execution path with its own gate
conditions and its own risk rules (max inventory skew, not SL/TP in the
traditional sense). It runs alongside the directional engine and never
forces trades through the main signal pipeline.

Paper mode: fills are simulated when the market trades through our quoted
levels (price <= bid for a buy fill, price >= ask for a sell fill). Every
fill and cycle is logged to the ``market_making`` table so fill-rate and
inventory behavior can be validated against the SpreadOptimizer-style
assumptions later (roadmap P2.2).
"""

import time as time_mod
from loguru import logger


class MarketMaker:
    def __init__(self, store, symbols: list[str] | None = None,
                 spread_pct: float = 0.0015,       # half-spread around mid
                 quote_size_usdt: float = 100.0,   # size quoted per side
                 max_inventory_usdt: float = 500.0,  # hard inventory cap
                 max_inventory_skew_pct: float = 0.5,  # skew = inv / cap
                 min_spread_pct: float = 0.0005,   # never quote tighter than this
                 max_inventory_to_quote_pct: float = 0.8,  # stop quoting into skew
                 fee_pct: float = 0.001,
                 state_manager=None):
        self.store = store
        self.symbols = symbols or []
        self.state_manager = state_manager
        self.fee_pct = fee_pct

        self.spread_pct = spread_pct
        self.quote_size_usdt = quote_size_usdt
        self.max_inventory_usdt = max_inventory_usdt
        self.max_inventory_skew_pct = max_inventory_skew_pct
        self.min_spread_pct = min_spread_pct
        self.max_inventory_to_quote_pct = max_inventory_to_quote_pct

        # Per-symbol state: inventory (signed units, +long/-short), avg entry
        self.inventory: dict[str, float] = {}
        self.avg_price: dict[str, float] = {}
        self.realized_pnl: dict[str, float] = {}
        self.fills: int = 0
        self.last_quote: dict[str, dict] = {}
        self.last_price: dict[str, float] = {}

    # ------------------------------------------------------------------ #
    # Risk rules — read live from risk_rules.yaml when a state manager exists
    # ------------------------------------------------------------------ #
    def _rules(self) -> dict:
        if self.state_manager is not None:
            try:
                params = self.state_manager.get_active_params()
                mm = params.get("market_making") or {}
                if mm:
                    return mm
            except Exception:
                pass
        return {}

    def _resolve(self, key: str, default):
        return float(self._rules().get(key, default))

    # ------------------------------------------------------------------ #
    # Per-cycle quoting + fill simulation (paper)
    # ------------------------------------------------------------------ #
    def cycle(self, current_prices: dict[str, float]) -> list[dict]:
        """Run one quoting/fill cycle. Returns the fills that occurred.

        Quotes both sides around mid. When the market trades through a quote
        (paper simulation), the fill is taken, inventory is updated, and PnL
        is realized against the opposite side.
        """
        fills = []
        if not current_prices:
            return fills

        for symbol in self.symbols:
            price = current_prices.get(symbol)
            if not price or price <= 0:
                continue
            fills += self._quote_and_fill(symbol, price)

        return fills

    def _quote_and_fill(self, symbol: str, price: float) -> list[dict]:
        """Quote around the PREVIOUS price, fill on the current price crossing
        the standing quotes (paper simulation). First cycle only quotes."""
        fills = []
        prev_price = self.last_price.get(symbol)
        self.last_price[symbol] = price
        if not prev_price:
            # No standing quote yet — quote for the next cycle, no fills.
            self._set_quote(symbol, price)
            return fills

        inv = self.inventory.get(symbol, 0.0)
        inv_usdt = abs(inv * price)
        cap = self._resolve("max_inventory_usdt", self.max_inventory_usdt)
        max_skew = self._resolve("max_inventory_skew_pct", self.max_inventory_skew_pct)

        # Inventory-skew gate: as inventory approaches the cap, quote only the
        # rebalancing side (sell into long inventory, buy into short) and stop
        # adding to the skew side entirely.
        skew_ratio = inv_usdt / cap if cap > 0 else 0.0
        stop_adding = skew_ratio >= max_skew
        quote_bid = True
        quote_ask = True
        if stop_adding:
            if inv > 0:
                quote_bid = False      # don't add more longs
            elif inv < 0:
                quote_ask = False      # don't add more shorts
            else:
                pass  # flat inventory — quote both

        spread = self._resolve("spread_pct", self.spread_pct)
        min_spread = self._resolve("min_spread_pct", self.min_spread_pct)
        half = max(spread / 2, min_spread / 2)
        bid = prev_price * (1 - half)
        ask = prev_price * (1 + half)
        qty = (self._resolve("quote_size_usdt", self.quote_size_usdt)) / prev_price

        # --- Paper fill simulation against the standing quotes ---
        # Buy fill: market trades at/below our bid -> we buy qty at bid.
        if quote_bid and price <= bid:
            fills.append(self._apply_fill(symbol, "buy", bid, qty, price))
        # Sell fill: market trades at/above our ask -> we sell qty at ask.
        if quote_ask and price >= ask:
            fills.append(self._apply_fill(symbol, "sell", ask, qty, price))

        self._set_quote(symbol, price, bid=bid, ask=ask, quote_bid=quote_bid,
                        quote_ask=quote_ask, skew_ratio=skew_ratio)

        # Inventory cap: hard-stop quoting (both sides) when inventory exceeds
        # the absolute cap regardless of skew settings — never lever past it.
        if inv_usdt >= cap:
            self.last_quote[symbol]["quoting"] = {"bid": False, "ask": False}

        return fills

    def _set_quote(self, symbol: str, price: float, bid: float | None = None,
                   ask: float | None = None, quote_bid: bool = True,
                   quote_ask: bool = True, skew_ratio: float = 0.0):
        inv = self.inventory.get(symbol, 0.0)
        spread = self._resolve("spread_pct", self.spread_pct)
        min_spread = self._resolve("min_spread_pct", self.min_spread_pct)
        half = max(spread / 2, min_spread / 2)
        self.last_quote[symbol] = {
            "bid": bid if bid is not None else price * (1 - half),
            "ask": ask if ask is not None else price * (1 + half),
            "price": price,
            "inventory": inv,
            "skew_ratio": round(skew_ratio, 3),
            "quoting": {"bid": quote_bid, "ask": quote_ask},
        }

    def _apply_fill(self, symbol: str, side: str, fill_price: float,
                    qty: float, mid: float) -> dict:
        """Update inventory + realized PnL for a simulated fill."""
        inv = self.inventory.get(symbol, 0.0)
        avg = self.avg_price.get(symbol, fill_price)
        fee = fill_price * qty * self.fee_pct
        realized = 0.0

        if side == "buy":
            if inv >= 0:
                # Adding to a long (or flat) — new avg price.
                new_qty = inv + qty
                self.avg_price[symbol] = (avg * inv + fill_price * qty) / new_qty if new_qty else fill_price
                self.inventory[symbol] = new_qty
            else:
                # Buying back a short — realize PnL on the closed portion.
                close_qty = min(qty, -inv)
                realized = (avg - fill_price) * close_qty - fee
                self.inventory[symbol] = inv + qty
                if self.inventory[symbol] >= 0:
                    self.avg_price[symbol] = fill_price
        else:  # sell
            if inv <= 0:
                new_qty = inv - qty
                self.avg_price[symbol] = (avg * inv - fill_price * qty) / new_qty if new_qty else fill_price
                self.inventory[symbol] = new_qty
            else:
                # Selling into a long — realize PnL on the closed portion.
                close_qty = min(qty, inv)
                realized = (fill_price - avg) * close_qty - fee
                self.inventory[symbol] = inv - qty
                if self.inventory[symbol] <= 0:
                    self.avg_price[symbol] = fill_price

        self.realized_pnl[symbol] = self.realized_pnl.get(symbol, 0.0) + realized
        self.fills += 1

        fill = {
            "timestamp": int(time_mod.time() * 1000),
            "symbol": symbol,
            "side": side,
            "price": round(fill_price, 8),
            "quantity": round(qty, 8),
            "fee": round(fee, 6),
            "inventory": round(self.inventory[symbol], 8),
            "inventory_value": round(self.inventory[symbol] * mid, 2),
            "realized_pnl": round(realized, 6),
        }
        logger.info(f"[MM] {side.upper()} {symbol} @ {fill_price:.4f} qty={qty:.4f} "
                    f"inv={self.inventory[symbol]:.4f} pnl={realized:.4f}")
        self._log_fill(fill)
        return fill

    def _log_fill(self, fill: dict):
        try:
            self.store.conn.execute(
                """INSERT OR IGNORE INTO market_making
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [fill["timestamp"], fill["symbol"], fill["side"], fill["price"],
                 fill["quantity"], fill["fee"], fill["inventory"],
                 fill["inventory_value"], fill["realized_pnl"]],
            )
        except Exception as e:
            logger.debug(f"MM log skip: {e}")

    # ------------------------------------------------------------------ #
    def status(self) -> dict:
        inventory_value = sum(
            inv * (q.get("price", 0))
            for sym, inv in self.inventory.items()
            if (q := self.last_quote.get(sym))
        )
        return {
            "enabled": bool(self.symbols),
            "symbols": self.symbols,
            "fills": self.fills,
            "total_realized_pnl": round(sum(self.realized_pnl.values()), 4),
            "inventory_value_usdt": round(inventory_value, 2),
            "per_symbol": {
                s: {
                    "inventory": round(self.inventory.get(s, 0.0), 8),
                    "realized_pnl": round(self.realized_pnl.get(s, 0.0), 4),
                    "quote": self.last_quote.get(s),
                }
                for s in self.symbols
            },
        }
