"""Regime detection — classify market state and weight strategies accordingly.
v0: ADX + realized-volatility thresholds.
v1: Hidden Markov Model (hmmlearn) — deferred.
v2: Hurst exponent — distinguishes mean-reverting vs trending regimes."""

import numpy as np
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class Regime(Enum):
    STRONG_TREND = "strong_trend"
    WEAK_TREND = "weak_trend"
    CHOPPY = "choppy"
    HIGH_VOL = "high_vol"
    MEAN_REVERTING = "mean_reverting"
    UNKNOWN = "unknown"


@dataclass
class RegimeResult:
    regime: Regime
    adx: float
    realized_vol: float
    vol_percentile: float
    hurst: float
    weights: dict[str, float]
    hmm_probs: list[float] | None = None
    hmm: dict | None = None
    m_regime: float = 1.0   # ADX/vol-derived position-size multiplier (spec §2.2)


class HMMRegimeDetector:
    """Hidden Markov Model regime detection.

    Requires hmmlearn + enough accumulated 15m closes; degrades silently
    (returns None) until trained, so the ADX/Hurst path stays authoritative.
    """

    N_STATES = 4

    def __init__(self, min_samples: int = 250, refit_every: int = 120):
        self.min_samples = min_samples
        self.refit_every = refit_every
        self._returns: list[float] = []
        self._prev_close: float = 0.0
        self._model = None
        self._state_stats: list[dict] = []
        self._points_seen = 0

    @staticmethod
    def _available() -> bool:
        try:
            import hmmlearn  # noqa: F401
            return True
        except ImportError:
            return False

    def update(self, close: float):
        if close is None or close <= 0:
            return
        if self._returns:
            if self._prev_close > 0:
                ret = (close - self._prev_close) / self._prev_close
                self._returns.append(float(ret))
            else:
                self._returns.append(0.0)
        else:
            self._returns.append(0.0)
        self._prev_close = close

        if len(self._returns) > 4000:
            self._returns = self._returns[-2000:]

        if self._model is None:
            if len(self._returns) >= self.min_samples and self._points_seen == 0:
                self._fit()
        elif len(self._returns) - self._points_seen >= self.refit_every:
            self._fit()

    def _fit(self):
        if not self._available() or len(self._returns) < self.min_samples:
            return
        try:
            from hmmlearn.hmm import GaussianHMM
            X = np.array(self._returns[-500:], dtype=float).reshape(-1, 1)
            model = GaussianHMM(n_components=3, covariance_type="diag",
                                n_iter=20, random_state=42)
            model.fit(X)
            self._model = model
            self._points_seen = len(self._returns)
            self._state_stats = self._compute_state_stats(model)
            logger.info(f"HMM trained: {len(X)} samples, {model.n_components} states")
        except Exception as e:
            logger.debug(f"HMM fit skipped: {e}")

    @staticmethod
    def _compute_state_stats(model) -> list[dict]:
        stats = []
        for s in range(model.n_components):
            mean = float(model.means_[s][0])
            covar = model.covars_[s]
            var = float(np.diag(covar)[0]) if model.covariance_type == "full" else float(covar)
            stats.append({"state": s, "mean": mean, "std": max(var, 0) ** 0.5})
        return stats

    def infer(self) -> dict | None:
        """Current state, probabilities, and mapped regime. None until trained."""
        if self._model is None or len(self._returns) < 20:
            return None
        try:
            X = np.array(self._returns[-20:], dtype=float).reshape(-1, 1)
            probs = self._model.predict_proba(X[-1:])[0]
            state = int(np.argmax(probs))
            return {
                "state": state,
                "probabilities": [round(float(p), 4) for p in probs],
                "regime": self._classify_state(state),
            }
        except Exception:
            return None

    def _classify_state(self, state: int) -> str:
        if not self._state_stats:
            return "unknown"
        st = next((s for s in self._state_stats if s["state"] == state), None)
        if st is None:
            return "unknown"
        stds = sorted(s["std"] for s in self._state_stats)
        median_std = stds[len(stds) // 2] if stds else 0.0
        if st["std"] > max(median_std * 1.8, 0.002):
            return "high_vol"
        if abs(st["mean"]) > max(median_std * 0.3, 0.0003):
            return "strong_trend"
        return "choppy"


def hurst_exponent(ts: np.ndarray, max_lag: int = 20) -> float:
    """Compute the Hurst exponent of a time series.

    H < 0.5 → mean-reverting
    H ≈ 0.5 → random walk (Brownian motion)
    H > 0.5 → trending (persistent)

    Uses the rescaled range (R/S) method.
    """
    if len(ts) < max_lag + 2:
        return 0.5

    ts = np.asarray(ts, dtype=float)
    if np.std(ts) == 0:
        return 0.5

    lags = range(2, min(max_lag, len(ts) - 1))
    rs_values = []

    for lag in lags:
        segments = len(ts) // lag
        if segments < 1:
            continue

        rs = []
        for i in range(segments):
            chunk = ts[i * lag: (i + 1) * lag]
            mean = np.mean(chunk)
            if np.std(chunk) == 0:
                continue
            deviations = chunk - mean
            z = np.cumsum(deviations)
            r = np.max(z) - np.min(z)
            s = np.std(chunk)
            if s > 0:
                rs.append(r / s)

        if rs:
            rs_values.append(np.mean(rs))

    if len(rs_values) < 4:
        return 0.5

    valid_lags = lags[:len(rs_values)]
    log_lags = np.log(valid_lags)
    log_rs = np.log(rs_values)

    poly = np.polyfit(log_lags, log_rs, 1)
    return float(poly[0])


class RegimeDetector:
    def __init__(self, adx_trend_threshold: float = 25.0,
                 vol_percentile_threshold: float = 80.0,
                 vol_lookback: int = 20,
                 hurst_lookback: int = 100,
                 regime_multipliers: dict | None = None):
        self.adx_threshold = adx_trend_threshold
        self.vol_threshold = vol_percentile_threshold
        self.vol_lookback = vol_lookback
        self.hurst_lookback = hurst_lookback
        self.regime_multipliers = regime_multipliers or {}
        self._vol_history: dict[str, list[float]] = {}
        self._price_history: dict[str, list[float]] = {}
        self.hmm: dict[str, HMMRegimeDetector] = {}

    def detect(self, market_data: dict[str, dict], symbol: str | None = None,
               multipliers: dict | None = None,
               adx_threshold: float | None = None,
               vol_threshold: float | None = None) -> RegimeResult:
        """Classify regime from multi-timeframe market data.

        State (vol/price history, HMM) is tracked per symbol so different coins'
        price series never mix in one estimator.
        """
        key = symbol or "default"
        price_history = self._price_history.setdefault(key, [])
        vol_history = self._vol_history.setdefault(key, [])
        hmm = self.hmm.setdefault(key, HMMRegimeDetector())

        adx_15m = market_data.get("15m", {}).get("adx", 20)
        adx_1h = market_data.get("1h", {}).get("adx", 20)

        # Track close price for Hurst computation (per symbol)
        close_15m = market_data.get("15m", {}).get("close", 0)
        if close_15m > 0:
            price_history.append(close_15m)
            if len(price_history) > self.hurst_lookback:
                price_history[:] = price_history[-self.hurst_lookback:]
            hmm.update(close_15m)

        vol_15m = market_data.get("15m", {}).get("atr_pct", 0.02)
        vol_history.append(vol_15m)
        if len(vol_history) > self.vol_lookback * 10:
            vol_history[:] = vol_history[-self.vol_lookback * 10:]

        recent_vols = vol_history[-self.vol_lookback:] if vol_history else [vol_15m]
        vol_percentile = np.percentile(recent_vols, self.vol_threshold)
        is_high_vol = vol_15m > vol_percentile

        adx_composite = (adx_15m + adx_1h) / 2

        # Compute Hurst from price history
        hurst = hurst_exponent(np.array(price_history), max_lag=20) if len(price_history) >= 30 else 0.5

        # Profile overrides (per-tick, hot-swappable): thresholds can be
        # tuned per mode (aggressive catches trends earlier, e.g. ADX ≥ 22).
        adx_trend = adx_threshold or self.adx_threshold
        vol_trend = vol_threshold or self.vol_threshold
        if vol_trend != self.vol_threshold:
            vol_percentile = np.percentile(recent_vols, vol_trend)
            is_high_vol = vol_15m > vol_percentile

        # Regime classification with Hurst refinement
        if adx_composite < 20:
            if hurst < 0.4:
                regime = Regime.MEAN_REVERTING
            else:
                regime = Regime.CHOPPY
        elif is_high_vol:
            regime = Regime.HIGH_VOL
        elif adx_composite >= adx_trend and hurst > 0.55:
            regime = Regime.STRONG_TREND
        elif hurst < 0.4:
            regime = Regime.MEAN_REVERTING
        else:
            regime = Regime.WEAK_TREND

        # HMM refinement: override into HIGH_VOL on panic states (liquidation risk).
        hmm_info = hmm.infer()
        hmm_probs = None
        if hmm_info and hmm_info.get("regime") == "high_vol":
            regime = Regime.HIGH_VOL
        if hmm_info:
            hmm_probs = hmm_info.get("probabilities")

        weights = self._compute_weights(regime, hurst)

        # ADX/vol regime multiplier M_regime — scales position sizing downstream.
        active_multipliers = multipliers or self.regime_multipliers or {}
        m_regime = float(active_multipliers.get(regime.value, 1.0))

        return RegimeResult(
            regime=regime,
            adx=round(adx_composite, 1),
            realized_vol=round(vol_15m, 4),
            vol_percentile=round(vol_percentile, 4),
            hurst=round(hurst, 3),
            weights=weights,
            hmm_probs=hmm_probs,
            hmm=hmm_info,
            m_regime=m_regime,
        )

    def _compute_weights(self, regime: Regime, hurst: float = 0.5) -> dict[str, float]:
        base = 1.0
        w = {
            "MovingAverageCross": base,
            "RSIMeanReversion": base,
            "Breakout": base,
            "BollingerReversion": base,
            "VolumeSpike": base,
        }

        if regime == Regime.STRONG_TREND:
            w["MovingAverageCross"] = 1.3
            w["Breakout"] = 1.2
            w["RSIMeanReversion"] = 0.3
            w["BollingerReversion"] = 0.4
            w["VolumeSpike"] = 0.8

        elif regime == Regime.WEAK_TREND:
            w["MovingAverageCross"] = 1.1
            w["Breakout"] = 1.0
            w["RSIMeanReversion"] = 0.6
            w["BollingerReversion"] = 0.7
            w["VolumeSpike"] = 0.9

        elif regime == Regime.CHOPPY:
            w["RSIMeanReversion"] = 1.3
            w["BollingerReversion"] = 1.2
            w["MovingAverageCross"] = 0.3
            w["Breakout"] = 0.4
            w["VolumeSpike"] = 0.7

        elif regime == Regime.HIGH_VOL:
            w["Breakout"] = 1.3
            w["VolumeSpike"] = 1.2
            w["MovingAverageCross"] = 0.6
            w["RSIMeanReversion"] = 0.3
            w["BollingerReversion"] = 0.5

        elif regime == Regime.MEAN_REVERTING:
            w["RSIMeanReversion"] = 1.5
            w["BollingerReversion"] = 1.5
            w["MovingAverageCross"] = 0.2
            w["Breakout"] = 0.2
            w["VolumeSpike"] = 0.5

        # Hurst fine-tuning: push weights further in the indicated direction
        if hurst < 0.4 and regime not in (Regime.MEAN_REVERTING, Regime.CHOPPY):
            w["RSIMeanReversion"] *= 1.2
            w["BollingerReversion"] *= 1.2
            w["MovingAverageCross"] *= 0.8
        elif hurst > 0.6 and regime not in (Regime.STRONG_TREND, Regime.WEAK_TREND):
            w["MovingAverageCross"] *= 1.2
            w["Breakout"] *= 1.2
            w["RSIMeanReversion"] *= 0.8

        total = sum(w.values())
        return {k: round(v / total, 3) for k, v in w.items()}
