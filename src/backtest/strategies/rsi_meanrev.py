"""RSI Mean Reversion — buy oversold, sell overbought."""

import backtrader as bt


class RSIMeanReversion(bt.Strategy):
    params = (
        ("rsi_period", 14),
        ("oversold", 35),
        ("overbought", 65),
        ("stop_loss_pct", 0.015),
        ("take_profit_pct", 0.03),
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
        self.sma = bt.indicators.SMA(self.data.close, period=20)
        self.order = None
        self.entry_price = None
        self.trades = []

    def get_trade_log(self) -> list[dict]:
        return self.trades

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.rsi[0] < self.params.oversold and self.data.close[0] < self.sma[0]:
                size = self.broker.getcash() * 0.02 / self.data.close[0]
                self.entry_price = self.data.close[0]
                self.order = self.buy(size=size)
            elif self.rsi[0] > self.params.overbought and self.data.close[0] > self.sma[0]:
                size = self.broker.getcash() * 0.02 / self.data.close[0]
                self.entry_price = self.data.close[0]
                self.order = self.sell(size=size)
        else:
            if self.position.size > 0 and self.rsi[0] > 55:
                self.order = self.close()
            elif self.position.size < 0 and self.rsi[0] < 45:
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
                "strategy": "RSIMeanReversion",
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
                rsi = d.get("rsi", 50)
                if isinstance(rsi, (int, float)):
                    if rsi < 35:
                        return {"action": "LONG", "confidence": round(max(0.4, 1 - rsi / 100), 3)}
                    elif rsi > 65:
                        return {"action": "SHORT", "confidence": round(max(0.4, rsi / 100), 3)}

        rsi = market_data.get("15m", {}).get("rsi", 50)
        if isinstance(rsi, (int, float)) and rsi < 35:
            return {"action": "LONG", "confidence": round(max(0.4, 1 - rsi / 100), 3)}
        return {"action": "HOLD", "confidence": 0.3}
