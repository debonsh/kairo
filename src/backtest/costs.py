"""Trading cost models — fees, slippage, spread."""


class CostModel:
    def __init__(self, taker_fee: float = 0.001, maker_fee: float = 0.001,
                 slippage_pct: float = 0.0005):
        self.taker_fee = taker_fee
        self.maker_fee = maker_fee
        self.slippage_pct = slippage_pct

    def entry_cost(self, price: float, size: float, side: str = "buy") -> float:
        notional = price * size
        fee = notional * self.taker_fee
        slippage = notional * self.slippage_pct
        return fee + slippage

    def exit_cost(self, price: float, size: float) -> float:
        return self.entry_cost(price, size)

    def round_trip_cost(self, entry_price: float, exit_price: float, size: float) -> float:
        return self.entry_cost(entry_price, size) + self.exit_cost(exit_price, size)

    def net_pnl(self, entry_price: float, exit_price: float, size: float, side: str = "long") -> float:
        gross = (exit_price - entry_price) * size if side == "long" else (entry_price - exit_price) * size
        costs = self.round_trip_cost(entry_price, exit_price, size)
        return gross - costs

    def breakeven_move(self, price: float, side: str = "long") -> float:
        return price * (self.taker_fee * 2 + self.slippage_pct * 2)

    def minimum_profitable_trade(self, price: float, min_rr: float = 1.5) -> dict:
        b_e = self.breakeven_move(price)
        return {
            "breakeven_move": round(b_e, 4),
            "min_target_pct": round(b_e / price * 100 * min_rr, 4),
            "cost_as_pct": round((self.taker_fee * 2 + self.slippage_pct * 2) * 100, 4),
        }
