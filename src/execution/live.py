"""Live trading execution — sends real orders to exchange."""

from loguru import logger
from .exchange import Exchange
from .paper import PaperTrader


class LiveTrader:
    def __init__(self, store, exchange: Exchange, paper: PaperTrader):
        self.store = store
        self.exchange = exchange
        self.paper = paper
        self.mode = "paper" if exchange.testnet else "live"

    def execute(self, decision: dict) -> dict | None:
        if not decision.get("executable"):
            logger.debug(f"Decision not executable: {decision.get('action', '?')}")
            return None

        trade = decision.get("trade", decision)
        symbol = trade.get("symbol", "")
        action = trade.get("action", decision.get("action", ""))
        size_usdt = trade.get("usdt_value", trade.get("size_usdt", 0))
        entry_price = trade.get("entry_price", 0)
        stop_loss = trade.get("stop_loss", 0)
        take_profit = trade.get("take_profit", 0)

        if size_usdt <= 0 or entry_price <= 0:
            return None

        quantity = size_usdt / entry_price

        if self.mode == "paper":
            trade = self.paper.open_position(
                symbol=symbol,
                side="buy" if action == "LONG" else "sell",
                entry_price=entry_price,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy=decision.get("strategy", "agent"),
            )
        else:
            if action == "LONG":
                self.exchange.market_buy(symbol, quantity)
            else:
                self.exchange.market_sell(symbol, quantity)

            trade = {
                "symbol": symbol,
                "side": action.lower(),
                "entry_price": entry_price,
                "quantity": quantity,
                "usdt_value": size_usdt,
                "exchange": self.exchange.exchange_id,
                "mode": "live",
            }
            logger.info(f"[LIVE] Executed {action} {symbol} @ {entry_price} | ${size_usdt}")

        return trade

    def get_portfolio(self) -> dict:
        if self.mode == "paper":
            return self.paper.get_portfolio()

        balance = self.exchange.fetch_balance()
        positions = self.exchange.api.fetch_positions() if hasattr(self.exchange.api, "fetch_positions") else []
        return {
            "balance": balance.get("total", 0),
            "free": balance.get("free", 0),
            "open_positions": len(positions),
            "positions": positions[:5],
        }

    def reconcile(self) -> dict:
        """Compare exchange state vs local DB. Trust the exchange on mismatch.

        Live mode only — paper mode has no exchange positions to compare.
        """
        if self.mode == "paper":
            return {"mode": "paper", "ok": True, "note": "paper mode — no exchange positions"}

        try:
            ex_positions = self.exchange.fetch_positions()
            db_positions = self.store.get_open_positions()

            def _norm(sym: str) -> str:
                return (sym or "").split(":")[0]

            ex_symbols = {
                _norm(p.get("symbol", ""))
                for p in ex_positions
                if float(p.get("contracts") or p.get("info", {}).get("size") or 0) != 0
            }
            db_symbols = {_norm(p["symbol"]) for p in db_positions}

            orphaned = sorted(ex_symbols - db_symbols)
            ghost = sorted(db_symbols - ex_symbols)

            if orphaned:
                logger.warning(f"RECONCILE: exchange has positions not in DB (trust exchange): {orphaned}")
            if ghost:
                logger.warning(f"RECONCILE: DB has positions not on exchange: {ghost}")

            return {
                "ok": True,
                "matched": len(ex_symbols & db_symbols),
                "orphaned": orphaned,
                "ghost": ghost,
            }
        except Exception as e:
            logger.warning(f"Reconcile failed: {e}")
            return {"ok": False, "error": str(e)}
