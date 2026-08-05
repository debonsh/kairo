"""Breakout strategy — buy when price breaks above recent high, sell below recent low."""

import backtrader as bt


class Breakout(bt.Strategy):
    params = (
        ("lookback", 20),
        ("volume_factor", 1.5),
        ("stop_loss_pct", 0.015),
        ("take_profit_pct", 0.03),
    )

    def __init__(self):
        self.highest = bt.indicators.Highest(self.data.high, period=self.params.lookback)
        self.lowest = bt.indicators.Lowest(self.data.low, period=self.params.lookback)
        self.avg_volume = bt.indicators.SMA(self.data.volume, period=self.params.lookback)
        self.order = None
        self.entry_price = None
        self.trades = []

    def get_trade_log(self) -> list[dict]:
        return self.trades

    def next(self):
        if self.order:
            return

        volume_confirmed = self.data.volume[0] > self.avg_volume[0] * self.params.volume_factor

        if not self.position:
            if self.data.close[0] > self.highest[-1] and volume_confirmed:
                size = self.broker.getcash() * 0.02 / self.data.close[0]
                self.entry_price = self.data.close[0]
                self.order = self.buy(size=size)
            elif self.data.close[0] < self.lowest[-1] and volume_confirmed:
                size = self.broker.getcash() * 0.02 / self.data.close[0]
                self.entry_price = self.data.close[0]
                self.order = self.sell(size=size)
        else:
            if self.position.size > 0 and self.data.close[0] < self.lowest[-1]:
                self.order = self.close()
            elif self.position.size < 0 and self.data.close[0] > self.highest[-1]:
                self.order = self.close()

            if self.entry_price:
                current = self.data.close[0]
                pnl_pct = abs((current - self.entry_price) / self.entry_price)
                if pnl_pct >= self.params.stop_loss_pct or pnl_pct >= self.params.take_profit_pct:
                    self.order = self.close()

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            self.trades.append({
                "symbol": self.data._name or "unknown",
                "strategy": "Breakout",
                "timeframe": "",
                "entry_time": str(trade.open_datetime()),
                "exit_time": str(trade.close_datetime()),
                "entry_price": trade.price,
                "exit_price": trade.price + trade.pnl / trade.size if trade.size else 0,
                "pnl": trade.pnlcomm,
                "pnl_pct": trade.pnl / self.broker.getvalue() * 100 if self.broker.getvalue() else 0,
                "equity_after": self.broker.getvalue(),
                "hold_hours": 0,
            })

    @staticmethod
    def evaluate(market_data: dict[str, dict]) -> dict:
        for tf in ["15m", "1h"]:
            if tf in market_data:
                d = market_data[tf]
                close = d.get("close", 0)
                high = d.get("high", 0)
                if high > 0 and close >= high * 0.995:
                    return {"action": "LONG", "confidence": 0.65}
                low = d.get("low", 0)
                if low > 0 and close <= low * 1.005:
                    return {"action": "SHORT", "confidence": 0.65}

        return {"action": "HOLD", "confidence": 0.2}
