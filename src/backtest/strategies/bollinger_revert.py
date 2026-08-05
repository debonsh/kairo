"""Bollinger Band Reversion — buy at lower band, sell at upper band."""

import backtrader as bt


class BollingerReversion(bt.Strategy):
    params = (
        ("period", 20),
        ("devfactor", 2.0),
        ("stop_loss_pct", 0.015),
        ("take_profit_pct", 0.03),
    )

    def __init__(self):
        self.bb = bt.indicators.BollingerBands(self.data.close,
                                                period=self.params.period,
                                                devfactor=self.params.devfactor)
        self.rsi = bt.indicators.RSI(self.data.close, period=14)
        self.order = None
        self.entry_price = None
        self.trades = []

    def get_trade_log(self) -> list[dict]:
        return self.trades

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.data.close[0] <= self.bb.bot[0] and self.rsi[0] < 40:
                size = self.broker.getcash() * 0.02 / self.data.close[0]
                self.entry_price = self.data.close[0]
                self.order = self.buy(size=size)
            elif self.data.close[0] >= self.bb.top[0] and self.rsi[0] > 60:
                size = self.broker.getcash() * 0.02 / self.data.close[0]
                self.entry_price = self.data.close[0]
                self.order = self.sell(size=size)
        else:
            if self.position.size > 0 and self.data.close[0] >= self.bb.mid[0]:
                self.order = self.close()
            elif self.position.size < 0 and self.data.close[0] <= self.bb.mid[0]:
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
                "strategy": "BollingerReversion",
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
                sma20 = d.get("sma20", 0)
                bb_lower = d.get("bb_lower", 0)
                bb_upper = d.get("bb_upper", 0)
                rsi = d.get("rsi", 50)

                if bb_lower and close <= bb_lower and (isinstance(rsi, (int, float)) and rsi < 40):
                    return {"action": "LONG", "confidence": 0.65}
                if bb_upper and close >= bb_upper and (isinstance(rsi, (int, float)) and rsi > 60):
                    return {"action": "SHORT", "confidence": 0.65}

        return {"action": "HOLD", "confidence": 0.2}
