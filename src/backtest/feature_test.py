"""Feature tester — backtest any feature to validate predictive value.
Before a feature (Fear & Greed, news sentiment, volume bars) gets
operational authority in the trading pipeline, it must prove itself
on holdout data.

ponytail: Granger causality + information coefficient. Simple, fast, effective."""

import numpy as np
from scipy import stats
from dataclasses import dataclass


@dataclass
class FeatureTestResult:
    feature_name: str
    predictive: bool
    information_coefficient: float
    p_value: float
    correlation: float
    sample_size: int
    notes: list[str]


class FeatureTester:
    def test_predictive_value(self, feature_series: np.ndarray,
                               returns_series: np.ndarray,
                               horizon: int = 5,
                               significance: float = 0.05) -> FeatureTestResult:
        """Test if a feature predicts future returns.

        feature_series: array of feature values (aligned to time)
        returns_series: array of forward returns (horizon bars ahead)
        horizon: how many bars forward to test
        significance: p-value threshold for statistical significance
        """
        if len(feature_series) < 30 or len(returns_series) < 30:
            return FeatureTestResult("unknown", False, 0.0, 1.0, 0.0,
                                     min(len(feature_series), len(returns_series)),
                                     ["insufficient data"])

        n = min(len(feature_series), len(returns_series))
        features = feature_series[-n:]
        forward_returns = returns_series[-n:]

        clean_mask = ~(np.isnan(features) | np.isnan(forward_returns))
        features = features[clean_mask]
        forward_returns = forward_returns[clean_mask]

        if len(features) < 30:
            return FeatureTestResult("unknown", False, 0.0, 1.0, 0.0,
                                     len(features), ["insufficient clean data"])

        ic = self._information_coefficient(features, forward_returns)

        correlation = np.corrcoef(features, forward_returns)[0, 1] if len(features) > 2 else 0
        correlation = 0.0 if np.isnan(correlation) else correlation

        p_value = self._granger_causality_test(features, forward_returns)

        predictive = abs(ic) > 0.02 and p_value < significance

        notes = []
        if abs(ic) <= 0.02:
            notes.append(f"IC too weak: {ic:.4f} (threshold: 0.02)")
        if p_value >= significance:
            notes.append(f"Not statistically significant: p={p_value:.4f}")
        if abs(correlation) < 0.05:
            notes.append("Correlation near zero — no linear relationship")
        if predictive:
            notes.append(f"Feature passes: IC={ic:.4f}, p={p_value:.4f}")

        return FeatureTestResult(
            feature_name="unknown",
            predictive=predictive,
            information_coefficient=round(float(ic), 4),
            p_value=round(float(p_value), 4),
            correlation=round(float(correlation), 4),
            sample_size=len(features),
            notes=notes,
        )

    def _information_coefficient(self, features: np.ndarray,
                                  forward_returns: np.ndarray) -> float:
        """Spearman rank correlation (Information Coefficient)."""
        ic, _ = stats.spearmanr(features, forward_returns)
        return float(ic) if not np.isnan(ic) else 0.0

    def _granger_causality_test(self, features: np.ndarray,
                                 forward_returns: np.ndarray) -> float:
        """Simple Granger causality-like test.
        Returns p-value: low values mean feature Granger-causes returns."""
        from sklearn.linear_model import LinearRegression

        if len(features) < 10:
            return 1.0

        X = np.column_stack([forward_returns[:-1], features[:-1]])
        y = forward_returns[1:]
        mask = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
        X, y = X[mask], y[mask]

        if len(X) < 10:
            return 1.0

        model_full = LinearRegression().fit(X, y)
        rss_full = np.sum((y - model_full.predict(X)) ** 2)

        X_reduced = X[:, 0].reshape(-1, 1)
        model_reduced = LinearRegression().fit(X_reduced, y)
        rss_reduced = np.sum((y - model_reduced.predict(X_reduced)) ** 2)

        if rss_full == 0:
            return 1.0

        f_stat = ((rss_reduced - rss_full) / 1) / (rss_full / (len(y) - 2))
        return float(1 - stats.f.cdf(f_stat, 1, len(y) - 2))
