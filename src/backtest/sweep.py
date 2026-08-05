"""VectorBT grid sweep — fast research backtests.
VectorBT is vectorized (NumPy backend), running 100x faster than
event-driven backtrader for parameter sweeps. Use for the scan phase,
then confirm top candidates in backtrader for realistic fill modeling."""

import numpy as np
from loguru import logger


class VectorBTSweep:
    """Lightweight wrapper — imports vectorbt on demand to avoid startup cost."""

    @staticmethod
    def sweep_strategy(prices: np.ndarray, strategy_type: str,
                       param_grid: dict) -> list[dict]:
        """Run a parameter grid search using vectorbt.

        prices: 1D array of close prices
        strategy_type: one of "ma_cross", "rsi", "breakout", "bb", "volume"
        param_grid: dict of param_name -> [values]

        Returns list of {params, sharpe, total_return, max_dd, win_rate, trades}
        """
        import vectorbt as vbt

        if strategy_type == "ma_cross":
            fast = vbt.IndicatorFactory.from_ta("talib", "SMA").run(prices, param_grid["fast_period"])
            slow = vbt.IndicatorFactory.from_ta("talib", "SMA").run(prices, param_grid["slow_period"])
            entries = fast.sma > slow.sma
            exits = fast.sma < slow.sma

        elif strategy_type == "rsi":
            rsi = vbt.IndicatorFactory.from_ta("talib", "RSI").run(prices, param_grid["rsi_period"])
            entries = rsi.real < param_grid["oversold"]
            exits = rsi.real > param_grid["overbought"]

        elif strategy_type == "breakout":
            high = vbt.IndicatorFactory.from_ta("talib", "MAX").run(prices, param_grid["lookback"])
            entries = prices > high.real.shift(1)
            exits = prices < high.real.shift(1)

        elif strategy_type == "bb":
            bb = vbt.IndicatorFactory.from_ta("talib", "BBANDS").run(
                prices, param_grid["period"], 2, 2
            )
            entries = prices < bb.real_lower
            exits = prices > bb.real_middle

        elif strategy_type == "volume":
            volume_data = param_grid.get("volume", np.ones_like(prices) * 1e6)
            avg_vol = vbt.MA.run(volume_data, param_grid["vol_period"])
            entries = (volume_data > avg_vol.ma * param_grid["vol_mult"]) & (prices > np.roll(prices, 1))
            exits = vbt.MA.run(prices, 10).ma < vbt.MA.run(prices, 30).ma

        else:
            return []

        portfolio = vbt.Portfolio.from_signals(
            prices, entries, exits,
            fees=0.001,
            freq="15min",
        )

        results = []
        stats = portfolio.stats()
        if len(stats.shape) > 0:
            for idx in np.ndindex(*stats.shape):
                s = stats.iloc[idx] if hasattr(stats, "iloc") else stats
                if s.get("Total Trades", 0) < 10:
                    continue
                results.append({
                    "sharpe": float(s.get("Sharpe Ratio", 0.0) or 0.0),
                    "total_return_pct": float(s.get("Total Return [%]", 0.0) or 0.0),
                    "max_drawdown_pct": float(s.get("Max Drawdown [%]", 0.0) or 0.0),
                    "win_rate_pct": float(s.get("Win Rate [%]", 0.0) or 0.0),
                    "total_trades": int(s.get("Total Trades", 0)),
                })

        return sorted(results, key=lambda r: r["sharpe"], reverse=True)[:20]

    @staticmethod
    def multi_coin_sweep(price_data: dict[str, np.ndarray],
                         strategy_types: list[str],
                         param_grids: dict[str, dict]) -> dict:
        """Sweep multiple coins × multiple strategy types.
        Returns {coin_strategy: [results sorted by Sharpe]}."""
        all_results = {}
        for coin, prices in price_data.items():
            for stype in strategy_types:
                grid = param_grids.get(stype, {})
                if not grid:
                    continue
                try:
                    results = VectorBTSweep.sweep_strategy(prices, stype, grid)
                    key = f"{coin}_{stype}"
                    all_results[key] = results
                    logger.info(f"Sweep {key}: {len(results)} valid combinations")
                except Exception as e:
                    logger.warning(f"Sweep failed {coin}_{stype}: {e}")
        return all_results


DEFAULT_PARAM_GRIDS = {
    "ma_cross": {
        "fast_period": [5, 8, 10, 12, 15],
        "slow_period": [20, 25, 30, 40, 50],
    },
    "rsi": {
        "rsi_period": [7, 10, 14, 20],
        "oversold": [25, 30, 35],
        "overbought": [65, 70, 75],
    },
    "breakout": {
        "lookback": [10, 15, 20, 30],
    },
    "bb": {
        "period": [10, 15, 20, 30],
    },
    "volume": {
        "vol_period": [10, 15, 20],
        "vol_mult": [1.5, 2.0, 2.5, 3.0],
    },
}
