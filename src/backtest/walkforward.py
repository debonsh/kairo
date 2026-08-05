"""Walk-forward optimization — time-series cross-validation for strategies."""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from loguru import logger


@dataclass
class WFOResult:
    windows: int
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    out_of_sample_trades: int
    is_overfit: bool
    consistency_score: float


def walkforward_analysis(
    oos_returns: list[float],
    is_returns: list[float] | None = None,
) -> WFOResult:
    """Walk-forward consistency analysis."""
    if not oos_returns:
        return WFOResult(0, 0, 0, 0, 0, 0, True, 0)

    returns = np.array(oos_returns)
    positive_windows = np.sum(returns > 0)
    total_windows = len(returns)
    consistency = positive_windows / total_windows if total_windows else 0

    total_return = np.prod(1 + np.array(oos_returns)) - 1 if len(oos_returns) else 0

    if len(returns) > 1:
        sharpe = np.sqrt(365) * np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
    else:
        sharpe = 0

    rolling_max = np.maximum.accumulate(np.cumprod(1 + np.array(oos_returns)))
    drawdown = (np.cumprod(1 + np.array(oos_returns)) - rolling_max) / rolling_max
    max_dd = np.min(drawdown) * 100 if len(drawdown) else 0

    win_count = np.sum([r > 0 for r in oos_returns])
    win_rate = win_count / len(oos_returns) * 100 if len(oos_returns) else 0

    is_overfit = False
    if is_returns and len(is_returns) > 0:
        is_sharpe = np.sqrt(365) * np.mean(is_returns) / np.std(is_returns) if np.std(is_returns) > 0 else 0
        if sharpe > 0 and is_sharpe > 0:
            is_overfit = is_sharpe > sharpe * 3

    return WFOResult(
        windows=total_windows,
        total_return_pct=round(total_return * 100, 2),
        sharpe_ratio=round(sharpe, 2),
        max_drawdown_pct=round(abs(max_dd), 2),
        win_rate_pct=round(win_rate, 2),
        out_of_sample_trades=total_windows,
        is_overfit=is_overfit,
        consistency_score=round(consistency, 2),
    )
