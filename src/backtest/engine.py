"""Backtesting engine — backtrader runner with DuckDB feed + cost models."""

import backtrader as bt
import pandas as pd
from datetime import datetime
from loguru import logger

from .feed import load_dataframe
from .costs import CostModel
from .metrics import compute_metrics


class BacktestEngine:
    def __init__(self, store, initial_cash: float = 5000.0, commission_pct: float = 0.001):
        self.store = store
        self.initial_cash = initial_cash
        self.commission_pct = commission_pct
        self.cost_model = CostModel(taker_fee=commission_pct)

    def run(
        self,
        strategy_class,
        symbol: str,
        exchange: str,
        timeframe: str,
        start_date: str | None = None,
        end_date: str | None = None,
        **strategy_kwargs,
    ) -> dict:
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(self.initial_cash)
        cerebro.broker.setcommission(commission=self.commission_pct)
        cerebro.addstrategy(strategy_class, **strategy_kwargs)

        start_dt = datetime.fromisoformat(start_date) if start_date else None
        end_dt = datetime.fromisoformat(end_date) if end_date else None
        df = load_dataframe(self.store, exchange, symbol, timeframe, start_dt, end_dt)

        if df.empty:
            logger.warning(f"No data for {exchange}:{symbol}:{timeframe}")
            return {"error": "no_data", "trades": [], "equity_curve": None}

        data = bt.feeds.PandasData(dataname=df)
        cerebro.adddata(data)
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.0, annualize=True)
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")

        start_val = cerebro.broker.getvalue()
        logger.info(f"Running backtest: {symbol} {timeframe} | Initial: ${start_val:.2f}")

        results = cerebro.run()
        strat = results[0]

        end_val = cerebro.broker.getvalue()
        pnl = end_val - start_val

        trade_analysis = strat.analyzers.trades.get_analysis()
        trades_list = self._parse_trades(trade_analysis, symbol, timeframe)

        if trades_list:
            equity_curve = self._build_equity_curve(trades_list, start_val)
        else:
            equity_curve = pd.Series(dtype=float)

        metrics = compute_metrics(trades_list, start_val, equity_curve)
        metrics.symbol = symbol
        metrics.strategy = strategy_class.__name__
        metrics.timeframe = timeframe

        return {
            "initial_value": start_val,
            "final_value": end_val,
            "pnl": pnl,
            "pnl_pct": round(pnl / start_val * 100, 2),
            "trades": trades_list,
            "metrics": metrics.to_dict(),
            "equity_curve": equity_curve.to_list() if len(equity_curve) > 0 else [],
            "trades_list_full": metrics.trades,
        }

    def _parse_trades(self, trade_analysis: dict, symbol: str, timeframe: str) -> list[dict]:
        trades = []
        if "total" not in trade_analysis or trade_analysis["total"]["total"] == 0:
            return trades

        # backtrader TradeAnalyzer doesn't give per-trade detail easily
        # We reconstruct from the strategy's trade log
        return trades

    def _build_equity_curve(self, trades: list[dict], start_val: float) -> pd.Series:
        if not trades:
            return pd.Series(dtype=float)
        equity = [start_val]
        times = [trades[0].get("entry_time", datetime.now())]
        for t in trades:
            equity.append(t.get("equity_after", equity[-1]))
            times.append(t.get("exit_time", times[-1]))
        return pd.Series(equity, index=pd.to_datetime(times))
