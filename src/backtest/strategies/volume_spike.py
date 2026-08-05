"""Volume Spike strategy — buy abnormal volume surges with price confirmation."""

import backtrader as bt


class VolumeSpike(bt.Strategy):
    params = (
        ("volume_period", 20),
        ("volume_multiplier", 2.5),
        ("price_change_min", 0.005),
        ("stop_loss_pct", 0.015),
        ("take_profit_pct", 0.03),
    )

    def __init__(self):
        self.avg_volume = bt.indicators.SMA(self.data.volume, period=self.params.volume_period)
        self.order = None
        self.entry_price = None
        self.trades = []

    def get_trade_log(self) -> list[dict]:
        return self.trades

    def next(self):
        if self.order:
            return

        volume_spike = self.data.volume[0] > self.avg_volume[0] * self.params.volume_multiplier
        price_change = (self.data.close[0] - self.data.close[-1]) / self.data.close[-1]

        if not self.position and volume_spike:
            if price_change > self.params.price_change_min:
                size = self.broker.getcash() * 0.02 / self.data.close[0]
                self.entry_price = self.data.close[0]
                self.order = self.buy(size=size)
            elif price_change < -self.params.price_change_min:
                size = self.broker.getcash() * 0.02 / self.data.close[0]
                self.entry_price = self.data.close[0]
                self.order = self.sell(size=size)
        elif self.position:
            bars_held = len(self) - len(self.trades)
            if bars_held > 10:
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
                "strategy": "VolumeSpike",
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
                vol = d.get("volume", 0)
                vol_ratio = d.get("volume_ratio", 1.0)
                if isinstance(vol_ratio, (int, float)) and vol_ratio > 2.0:
                    close = d.get("close", 0)
                    prev_close = d.get("open", 0)
                    if close > prev_close * 1.01:
                        return {"action": "LONG", "confidence": 0.55}
                    elif close < prev_close * 0.99:
                        return {"action": "SHORT", "confidence": 0.55}

        return {"action": "HOLD", "confidence": 0.15}
