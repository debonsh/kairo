"""Moving Average Crossover — trend-following strategy.
Buy when fast MA crosses above slow MA. Sell when fast crosses below."""

import backtrader as bt
import numpy as np


class MovingAverageCross(bt.Strategy):
    params = (
        ("fast_period", 10),
        ("slow_period", 30),
        ("stop_loss_pct", 0.015),
        ("take_profit_pct", 0.03),
    )

    def __init__(self):
        self.fast_ma = bt.indicators.SMA(self.data.close, period=self.params.fast_period)
        self.slow_ma = bt.indicators.SMA(self.data.close, period=self.params.slow_period)
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)
        self.order = None
        self.entry_price = None
        self.trades = []

    def get_trade_log(self) -> list[dict]:
        return self.trades

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.crossover > 0:
                size = self.broker.getcash() * 0.02 / self.data.close[0]
                self.entry_price = self.data.close[0]
                self.order = self.buy(size=size)
        else:
            if self.crossover < 0:
                self.order = self.close()

        if self.position and self.entry_price:
            current = self.data.close[0]
            pnl_pct = (current - self.entry_price) / self.entry_price if self.position.size > 0 else (
                self.entry_price - current) / self.entry_price
            if pnl_pct <= -self.params.stop_loss_pct or pnl_pct >= self.params.take_profit_pct:
                self.order = self.close()

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            self.trades.append({
                "symbol": self.data._name or "unknown",
                "strategy": "MovingAverageCross",
                "timeframe": "",
                "entry_time": trade.open_datetime().isoformat() if trade.open_datetime() else "",
                "exit_time": trade.close_datetime().isoformat() if trade.close_datetime() else "",
                "entry_price": trade.price,
                "exit_price": trade.price + trade.pnl / trade.size if trade.size else 0,
                "pnl": trade.pnlcomm,
                "pnl_pct": trade.pnl / self.broker.getvalue() * 100 if self.broker.getvalue() else 0,
                "equity_after": self.broker.getvalue(),
                "hold_hours": 0,
            })

    @staticmethod
    def evaluate(market_data: dict[str, dict]) -> dict:
        """Real-time evaluation without Cerebro. Uses SMA20/SMA50 from data."""
        sma20 = None
        sma50 = None
        close = None
        for tf in ["15m", "1h"]:
            if tf in market_data:
                d = market_data[tf]
                sma20 = sma20 or d.get("sma20")
                sma50 = sma50 or d.get("sma50")
                close = close or d.get("close")

        if sma20 and sma50 and sma20 > sma50:
            confidence = min(0.7, (sma20 - sma50) / sma20 * 10 + 0.4)
            return {"action": "LONG", "confidence": round(confidence, 3)}
        elif sma20 and sma50:
            return {"action": "HOLD", "confidence": 0.3}

        return {"action": "HOLD", "confidence": 0.0}
