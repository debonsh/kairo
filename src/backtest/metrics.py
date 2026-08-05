"""Performance metrics — Sharpe, Sortino, Calmar, drawdown, win rate."""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field


@dataclass
class BacktestResult:
    symbol: str
    strategy: str
    timeframe: str
    start_date: str
    end_date: str
    initial_capital: float
    final_equity: float
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_pct: float
    max_drawdown_duration_days: float
    win_rate_pct: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win_pct: float
    avg_loss_pct: float
    avg_hold_hours: float
    trades: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "trades"}


def compute_metrics(trades: list[dict], initial_capital: float, equity_curve: pd.Series | None = None) -> BacktestResult:
    if not trades:
        return BacktestResult(
            symbol="", strategy="", timeframe="", start_date="", end_date="",
            initial_capital=initial_capital, final_equity=initial_capital,
            total_return_pct=0, annualized_return_pct=0,
            sharpe_ratio=0, sortino_ratio=0, calmar_ratio=0,
            max_drawdown_pct=0, max_drawdown_duration_days=0,
            win_rate_pct=0, profit_factor=0,
            total_trades=0, winning_trades=0, losing_trades=0,
            avg_win_pct=0, avg_loss_pct=0, avg_hold_hours=0,
        )

    winners = [t for t in trades if t["pnl"] > 0]
    losers = [t for t in trades if t["pnl"] <= 0]
    total_trades = len(trades)
    win_rate = len(winners) / total_trades * 100 if total_trades else 0

    total_wins = sum(t["pnl"] for t in winners) if winners else 0
    total_losses = abs(sum(t["pnl"] for t in losers)) if losers else 0
    profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

    avg_win = np.mean([t["pnl_pct"] for t in winners]) if winners else 0
    avg_loss = abs(np.mean([t["pnl_pct"] for t in losers])) if losers else 0

    final_equity = trades[-1]["equity_after"] if trades else initial_capital
    total_return = (final_equity - initial_capital) / initial_capital * 100

    max_drawdown, max_dd_duration = _calc_drawdown(equity_curve) if equity_curve is not None else (0, 0)

    returns = equity_curve.pct_change().dropna() if equity_curve is not None else pd.Series(dtype=float)
    sharpe = _annualized_sharpe(returns) if len(returns) > 1 else 0
    sortino = _sortino_ratio(returns) if len(returns) > 1 else 0
    calmar = abs(total_return / max_drawdown) if max_drawdown > 0 else 0

    total_days = _calc_period_days(trades)
    annualized_return = ((1 + total_return / 100) ** (365 / total_days) - 1) * 100 if total_days > 0 else total_return

    avg_hold_hours = np.mean([t.get("hold_hours", 0) for t in trades]) if trades else 0

    return BacktestResult(
        symbol=trades[0].get("symbol", ""),
        strategy=trades[0].get("strategy", ""),
        timeframe=trades[0].get("timeframe", ""),
        start_date=str(trades[0].get("entry_time", "")),
        end_date=str(trades[-1].get("exit_time", "")),
        initial_capital=initial_capital,
        final_equity=final_equity,
        total_return_pct=round(total_return, 2),
        annualized_return_pct=round(annualized_return, 2),
        sharpe_ratio=round(sharpe, 2),
        sortino_ratio=round(sortino, 2),
        calmar_ratio=round(calmar, 2),
        max_drawdown_pct=round(max_drawdown, 2),
        max_drawdown_duration_days=round(max_dd_duration, 1),
        win_rate_pct=round(win_rate, 2),
        profit_factor=round(profit_factor, 2),
        total_trades=total_trades,
        winning_trades=len(winners),
        losing_trades=len(losers),
        avg_win_pct=round(avg_win, 2),
        avg_loss_pct=round(avg_loss, 2),
        avg_hold_hours=round(avg_hold_hours, 1),
        trades=trades,
    )


def _calc_drawdown(equity_curve: pd.Series) -> tuple[float, float]:
    rolling_max = equity_curve.expanding().max()
    drawdowns = (equity_curve - rolling_max) / rolling_max * 100
    max_dd = drawdowns.min()

    in_drawdown = drawdowns < 0
    dd_durations = []
    count = 0
    for val in in_drawdown:
        if val:
            count += 1
        else:
            if count:
                dd_durations.append(count)
            count = 0
    if count:
        dd_durations.append(count)
    max_dd_duration = max(dd_durations) * _estimate_bar_frequency(equity_curve) if dd_durations else 0

    return abs(max_dd), max_dd_duration


def _estimate_bar_frequency(series: pd.Series) -> float:
    if len(series) < 2:
        return 1.0
    diffs = series.index.to_series().diff().dropna()
    return diffs.median().total_seconds() / 86400


def _annualized_sharpe(returns: pd.Series, risk_free: float = 0.0) -> float:
    excess = returns - risk_free / 365
    return np.sqrt(365) * excess.mean() / excess.std() if excess.std() > 0 else 0


def _sortino_ratio(returns: pd.Series, risk_free: float = 0.0) -> float:
    excess = returns - risk_free / 365
    downside = excess[excess < 0]
    return np.sqrt(365) * excess.mean() / downside.std() if len(downside) > 0 and downside.std() > 0 else 0


def _calc_period_days(trades: list[dict]) -> float:
    import time
    try:
        first = min(t.get("entry_time", 0) for t in trades)
        last = max(t.get("exit_time", 0) for t in trades)
        if isinstance(first, str):
            first = time.mktime(time.strptime(first[:10], "%Y-%m-%d"))
        if isinstance(last, str):
            last = time.mktime(time.strptime(last[:10], "%Y-%m-%d"))
        return max((last - first) / 86400, 1)
    except (ValueError, TypeError):
        return 30
