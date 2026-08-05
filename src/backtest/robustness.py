"""Purged K-Fold, Deflated Sharpe, and PBO for robust backtesting."""

import numpy as np
from itertools import combinations
from loguru import logger


def purged_kfold(n_samples: int, n_splits: int = 5, purge_pct: float = 0.01) -> list[tuple[np.ndarray, np.ndarray]]:
    """Purged K-Fold cross-validation for time series.
    Returns list of (train_indices, test_indices)."""
    indices = np.arange(n_samples)
    purge = int(n_samples * purge_pct)
    fold_size = n_samples // n_splits
    splits = []
    for i in range(n_splits):
        test_start = i * fold_size
        test_end = min((i + 1) * fold_size, n_samples)
        test_idx = indices[test_start:test_end]

        train_idx = np.concatenate([
            indices[:max(0, test_start - purge)],
            indices[min(n_samples, test_end + purge):]
        ])
        splits.append((train_idx, test_idx))
    return splits


def combinatorial_purged_cv(
    n_samples: int, n_splits: int = 6, n_test_splits: int = 2,
    purge_pct: float = 0.01, embargo_pct: float = 0.01,
) -> list[list[tuple[np.ndarray, np.ndarray]]]:
    """Combinatorial purged cross-validation (López de Prado, Ch. 12).

    Splits the sample into n_splits groups and builds C(n_splits, n_test_splits)
    backtest paths. Each path tests a different combination of test groups and
    trains on the complement, with purge (label-window overlap) + embargo
    (serial-correlation memory). Returns list of paths, each a list of
    (train_idx, test_idx) folds.

    Multiple paths → probability of backtest overfitting (PBO) via
    prob_backtest_overfitting() across path IS/OOS Sharpe pairs.
    """
    from itertools import combinations

    indices = np.arange(n_samples)
    group_size = n_samples // n_splits
    if group_size < 1 or n_test_splits >= n_splits:
        return []

    purge = int(n_samples * purge_pct)
    embargo = int(n_samples * embargo_pct)
    groups = [indices[i * group_size: (i + 1) * group_size] for i in range(n_splits)]

    paths = []
    for test_combo in combinations(range(n_splits), n_test_splits):
        folds = []
        for g in test_combo:
            test_idx = groups[g]
            start = max(0, g * group_size - purge)
            end = min(n_samples, (g + 1) * group_size + purge + embargo)
            train_mask = np.ones(n_samples, dtype=bool)
            train_mask[start:end] = False
            folds.append((indices[train_mask], test_idx))
        paths.append(folds)
    return paths


def deflated_sharpe(sharpe_ratios: list[float], n_trials: int,
                    skew: float = -3.0, kurt: float = 7.0) -> float:
    """Deflated Sharpe Ratio — corrects for multiple testing bias.
    Higher is better; values above 0.0 are statistically significant."""
    if not sharpe_ratios or n_trials < 1:
        return 0.0

    sr = np.array(sharpe_ratios) if not isinstance(sharpe_ratios, np.ndarray) else sharpe_ratios
    n = len(sr)
    e_max = expected_max_sharpe(n, n_trials, skew, kurt)
    excess = np.mean(sr) - e_max
    std_est = np.std(sr) if np.std(sr) > 0 else 0.001
    return excess / (std_est * np.sqrt(1 - 1 / n)) if n > 1 else 0.0


def expected_max_sharpe(n: int, n_trials: int, skew: float = -3.0, kurt: float = 7.0) -> float:
    """Expected maximum Sharpe ratio from n_trials of n observations each."""
    if n < 1 or n_trials < 1:
        return 0.0
    gamma = 0.5772156649  # Euler-Mascheroni constant
    z = (1 - gamma) * _inverse_std_normal(1 - 1 / n_trials) + gamma * _inverse_std_normal(1 - 1 / (n_trials * np.e))

    # Edgeworth expansion for skew and kurtosis
    edgeworth = z + (1 / 6) * skew * (z ** 2 - 1) + (1 / 24) * (kurt - 3) * z * (z ** 2 - 3) - (1 / 36) * (skew ** 2) * z * (2 * z ** 2 - 5)
    return edgeworth / np.sqrt(n)


def _inverse_std_normal(p: float) -> float:
    """Approximation of inverse standard normal CDF."""
    if p <= 0 or p >= 1:
        return 0.0
    from scipy.stats import norm
    return norm.ppf(p)


def prob_backtest_overfitting(
    sharpe_is_list: list[float],
    sharpe_oos_list: list[float],
    n_combinations: int | None = None,
) -> float:
    """Probability of Backtest Overfitting (PBO).
    Values > 0.5 indicate likely overfitting."""
    if len(sharpe_is_list) != len(sharpe_oos_list) or len(sharpe_is_list) < 2:
        return 1.0

    sr_is = np.array(sharpe_is_list)
    sr_oos = np.array(sharpe_oos_list)
    n = len(sr_is)

    if n_combinations is None:
        n_combinations = min(100, n * (n - 1) // 2)

    combos = list(combinations(range(n), 2))
    if len(combos) > n_combinations:
        idx = np.random.choice(len(combos), n_combinations, replace=False)
        combos = [combos[i] for i in idx]

    relative_rankings = []
    for i, j in combos:
        is_diff = sr_is[i] - sr_is[j]
        oos_diff = sr_oos[i] - sr_oos[j]
        relative_rankings.append(int(is_diff * oos_diff < 0))

    pbo = np.mean(relative_rankings) if relative_rankings else 0.5
    return float(pbo)
