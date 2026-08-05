"""Paper trading simulator — mirrors real exchange behavior without risking capital."""

from datetime import datetime
from loguru import logger


class PaperTrader:
    def __init__(self, store, initial_balance: float = 5000.0, fee_pct: float = 0.001):
        self.store = store
        self.balance = initial_balance
        self.equity = initial_balance
        self.fee_pct = fee_pct
        self.open_trades: list[dict] = []
        self.trade_log: list[dict] = []

    def open_position(self, symbol: str, side: str, entry_price: float, quantity: float,
                      stop_loss: float, take_profit: float, strategy: str = "agent") -> dict | None:
        usdt_value = entry_price * quantity
        fee = usdt_value * self.fee_pct
        total_cost = usdt_value + fee

        if total_cost > self.balance:
            logger.warning(f"Insufficient balance: need ${total_cost:.2f}, have ${self.balance:.2f}")
            return None

        trade = {
            "exchange": "paper",
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "exit_price": None,
            "quantity": quantity,
            "usdt_value": usdt_value,
            "entry_time": int(datetime.now().timestamp() * 1000),
            "exit_time": None,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "strategy": strategy,
            "status": "open",
            "pnl": None,
            "pnl_pct": None,
        }

        trade_id = self.store.log_trade(trade)
        trade["id"] = trade_id
        self.balance -= total_cost
        self.open_trades.append(trade)
        logger.info(f"[PAPER] Opened {side} {symbol} @ {entry_price} | ${usdt_value:.2f} | Balance: ${self.balance:.2f}")
        return trade

    def close_position(self, trade: dict, exit_price: float, reason: str = "manual"):
        fee = exit_price * trade["quantity"] * self.fee_pct
        gross_pnl = (exit_price - trade["entry_price"]) * trade["quantity"]
        if trade["side"] == "short":
            gross_pnl = -gross_pnl
        net_pnl = gross_pnl - fee * 2

        trade_id = trade.get("id", "")
        trade["exit_price"] = exit_price
        trade["exit_time"] = int(datetime.now().timestamp() * 1000)
        trade["pnl"] = net_pnl
        trade["pnl_pct"] = net_pnl / (trade["entry_price"] * trade["quantity"]) * 100
        trade["status"] = "closed"
        trade["exit_reason"] = reason

        self.store.update_trade_exit(
            trade_id, exit_price, trade["exit_time"], reason,
            pnl=net_pnl, pnl_pct=trade["pnl_pct"],
        )
        self.balance += exit_price * trade["quantity"] - fee
        self.trade_log.append(trade)

        # Remove from open_trades by ID (DB dict ≠ memory dict by value)
        self.open_trades = [t for t in self.open_trades if t.get("id") != trade_id]

        logger.info(f"[PAPER] Closed {trade['symbol']} @ {exit_price} | PnL: ${net_pnl:.2f} "
                   f"({trade['pnl_pct']:.1f}%) | reason={reason} | Balance: ${self.balance:.2f}")
        return trade

    def check_stops(self, current_prices: dict[str, float]):
        for trade in list(self.open_trades):
            symbol = trade["symbol"]
            if symbol not in current_prices:
                continue

            price = current_prices[symbol]
            sl = trade["stop_loss"]
            tp = trade["take_profit"]

            if trade["side"] in ("long", "buy"):
                if price <= sl:
                    self.close_position(trade, price, "stop_loss")
                elif price >= tp:
                    self.close_position(trade, price, "take_profit")
            else:
                if price >= sl:
                    self.close_position(trade, price, "stop_loss")
                elif price <= tp:
                    self.close_position(trade, price, "take_profit")

    def get_portfolio(self) -> dict:
        current_equity = self.balance
        for t in self.open_trades:
            if t.get("exit_price") is None:
                current_equity += t["entry_price"] * t["quantity"]

        return {
            "balance": self.balance,
            "equity": current_equity,
            "open_positions": len(self.open_trades),
            "open_trades": self.open_trades,
            "recent_trades": self.trade_log[-20:],
            "total_trades": len(self.trade_log),
            "daily_pnl": sum(t.get("pnl", 0) for t in self.trade_log
                           if t.get("exit_time", 0) > int(datetime.now().replace(hour=0, minute=0).timestamp() * 1000)),
        }

    def partial_close(self, trade: dict, exit_price: float):
        """Close a partial position (e.g. 50%% at partial TP).
        Logs it as a separate trade entry so PnL tracking works correctly."""
        fee = exit_price * trade["quantity"] * self.fee_pct
        gross_pnl = (exit_price - trade["entry_price"]) * trade["quantity"]
        if trade["side"] == "short":
            gross_pnl = -gross_pnl
        net_pnl = gross_pnl - fee * 2

        partial_log = {
            "exchange": "paper",
            "symbol": trade["symbol"],
            "side": trade["side"],
            "entry_price": trade["entry_price"],
            "exit_price": exit_price,
            "quantity": trade["quantity"],
            "usdt_value": exit_price * trade["quantity"],
            "entry_time": trade.get("entry_time", 0),
            "exit_time": int(datetime.now().timestamp() * 1000),
            "pnl": net_pnl,
            "pnl_pct": net_pnl / (trade["entry_price"] * trade["quantity"] + 1e-12) * 100,
            "status": "closed",
            "exit_reason": trade.get("exit_reason", "partial_tp"),
            "strategy": trade.get("strategy", ""),
        }
        self.trade_log.append(partial_log)
        self.balance += exit_price * trade["quantity"] - fee
        logger.info(f"[PAPER] Partial close {trade['symbol']} x {trade['quantity']:.4f} @ {exit_price:.2f} | "
                   f"PnL: ${net_pnl:.2f} | Balance: ${self.balance:.2f}")

    def close_all(self, reason: str = "kill_switch"):
        for trade in list(self.open_trades):
            self.close_position(trade, trade["entry_price"] * 0.99, reason)
        logger.warning(f"All positions closed: {reason}")
