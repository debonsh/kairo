"""Meta-labeling with asymmetric triple-barrier targets.

Spec §3.1 (Aggressive Growth): replace fixed time-bar targets with dynamic,
ATR-based asymmetric barriers:
  Upper barrier (take profit): Entry + 3.0 × ATR₁₄
  Lower barrier (stop loss):   Entry − 1.0 × ATR₁₄
  Time barrier:                dynamic timedelta (4h) evaluated with REAL
                               timestamp deltas (not bar counts), so the
                               label is robust to volume-bar density changes.

Based on López de Prado, Advances in Financial Machine Learning, Chapter 3.
"""

from dataclasses import dataclass

import numpy as np
from loguru import logger


@dataclass
class TripleBarrierTarget:
    """Asymmetric triple-barrier target schema (spec §3.1)."""
    pt_multiplier: float = 3.0   # High reward-to-risk (3:1)
    sl_multiplier: float = 1.0   # Tight risk control
    time_limit_hours: int = 4    # Max holding duration


@dataclass
class LabelResult:
    label: int          # 1 = profitable, 0 = noise/loss
    outcome: str        # "profit_target" | "stop_loss" | "timeout"
    return_at_exit: float
    bars_held: int


class TripleBarrierLabeler:
    """Labels signals with asymmetric ATR-based triple barriers.

    Barriers are sized from the ATR *at the signal index* (absolute price
    units), giving a constant-volatility 3:1 payout structure. The time
    barrier is enforced with real millisecond timestamps when available so
    that a signal is never held past ``time_limit_hours`` regardless of bar
    density.
    """

    def __init__(self, pt_factor: float = 3.0, sl_factor: float = 1.0,
                 max_hold_bars: int = 96, time_limit_hours: int = 4):
        self.pt_factor = pt_factor
        self.sl_factor = sl_factor
        self.max_hold_bars = max_hold_bars   # scan window (96 × 15m = 24h)
        self.time_limit_hours = time_limit_hours

    def label(self, signals: list[dict], prices: np.ndarray,
              volatility: np.ndarray | None = None,
              timestamps: np.ndarray | None = None) -> list[LabelResult]:
        """Triple-barrier labeling for each signal.

        signals:    [{"index": int, "entry_price": float, "direction": str,
                      "timestamp": ms (optional)}, ...]
        prices:     1D array of close prices after each signal point
        volatility: 1D array of ATR values (absolute price units) aligned with
                    prices — dynamic barrier sizing. If omitted, falls back to
                    a 2% of price proxy (legacy behavior).
        timestamps: 1D array of ms epoch timestamps aligned with prices — used
                    for the real-time-delta time barrier. If omitted, the time
                    barrier falls back to ``max_hold_bars``.
        """
        results = []
        time_limit_ms = self.time_limit_hours * 3_600_000

        for sig in signals:
            idx = sig.get("index", 0)
            entry = sig.get("entry_price") or (prices[idx] if 0 <= idx < len(prices) else 0)
            direction = sig.get("direction", "long")

            if idx + 1 >= len(prices) or entry <= 0:
                results.append(LabelResult(0, "timeout", 0.0, 0))
                continue

            pt_level, sl_level = self._barrier_levels(sig, idx, entry, direction, prices, volatility)

            entry_ts = sig.get("timestamp")
            if entry_ts is None and timestamps is not None and idx < len(timestamps):
                entry_ts = timestamps[idx]

            scan_end = min(idx + 1 + self.max_hold_bars, len(prices))
            result = None
            window_end_price = entry

            for i in range(idx + 1, scan_end):
                price = prices[i]
                window_end_price = price

                # Real-timestamp time barrier — never hold past the limit.
                if entry_ts and timestamps is not None and i < len(timestamps):
                    if timestamps[i] > entry_ts + time_limit_ms:
                        break

                if direction == "long":
                    if price >= pt_level:
                        result = LabelResult(1, "profit_target", price / entry - 1, i - idx)
                        break
                    if price <= sl_level:
                        result = LabelResult(0, "stop_loss", price / entry - 1, i - idx)
                        break
                else:
                    if price <= pt_level:
                        result = LabelResult(1, "profit_target", entry / price - 1, i - idx)
                        break
                    if price >= sl_level:
                        result = LabelResult(0, "stop_loss", entry / price - 1, i - idx)
                        break

            if result is None:
                ret = (window_end_price / entry - 1) if direction == "long" \
                    else (entry / window_end_price - 1)
                results.append(LabelResult(0, "timeout", ret, scan_end - 1 - idx))
            else:
                results.append(result)

        return results

    def _barrier_levels(self, sig: dict, idx: int, entry: float, direction: str,
                        prices: np.ndarray, volatility: np.ndarray | None):
        """ATR-based asymmetric barriers (spec §3.1), with price-% fallback."""
        atr = None
        if volatility is not None and idx < len(volatility) and volatility[idx] > 0:
            atr = float(volatility[idx])

        if atr:
            pt_level = entry + atr * self.pt_factor if direction == "long" \
                else entry - atr * self.pt_factor
            sl_level = entry - atr * self.sl_factor if direction == "long" \
                else entry + atr * self.sl_factor
        else:
            # Legacy fallback: barriers as a fraction of price.
            vol = entry * 0.02
            pt_level = entry + vol * self.pt_factor if direction == "long" \
                else entry - vol * self.pt_factor
            sl_level = entry - vol * self.sl_factor if direction == "long" \
                else entry + vol * self.sl_factor

        return pt_level, sl_level


class MetaLabelClassifier:
    """Trains a classifier on triple-barrier labels to filter strategy signals.

    Sample-size discipline (roadmap P0.4): every prediction carries the
    training sample size and a ``trusted`` flag. A RandomForest retrained on a
    few dozen live outcomes is still mostly noise — same skepticism FuturesGate
    applies to Sharpe/win-rate readings. ``min_trusted_samples`` (default 100)
    gates the ``trusted`` flag; consumers should treat low-trust predictions as
    advisory.
    """

    def __init__(self, min_trusted_samples: int = 100):
        self.model = None
        self._trained = False
        self.training_samples = 0
        self.min_trusted_samples = min_trusted_samples

    def train(self, features: np.ndarray, labels: np.ndarray):
        from sklearn.ensemble import RandomForestClassifier

        if len(np.unique(labels)) < 2:
            logger.warning("Meta-labeler: only one class present, skipping training")
            self._trained = False
            return

        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=5,
            min_samples_leaf=10,
            class_weight="balanced",
            random_state=42,
        )
        self.model.fit(features, labels)
        self._trained = True
        self.training_samples = int(len(features))
        logger.info(f"Meta-labeler trained: {len(features)} samples, "
                    f"class balance: {np.mean(labels):.1%} positive, "
                    f"trusted={self.training_samples >= self.min_trusted_samples}")

    def predict(self, features: np.ndarray) -> dict:
        if not self._trained or self.model is None:
            return {"signal_valid": True, "confidence": 0.5, "reason": "untrained",
                    "sample_size": self.training_samples, "trusted": False}

        proba = self.model.predict_proba(features.reshape(1, -1))[0]
        pos_class = 1 if self.model.classes_[1] == 1 else 0
        confidence = float(proba[pos_class])
        trusted = self.training_samples >= self.min_trusted_samples

        return {
            "signal_valid": confidence > 0.55,
            "confidence": round(confidence, 3),
            "reason": f"RF confidence: {confidence:.3f}",
            "sample_size": self.training_samples,
            "trusted": trusted,
            "caveat": None if trusted else (
                f"meta-model trained on only {self.training_samples}/{self.min_trusted_samples} "
                f"live outcomes — treat p as advisory"),
        }

    @property
    def is_trained(self) -> bool:
        return self._trained


def build_meta_features(signal: dict, market_data: dict) -> np.ndarray:
    """Build feature vector for meta-labeling from signal context.

    Features:
    - Strategy name (one-hot or index)
    - RSI at signal time
    - Volatility (ATR / price)
    - Volume ratio (current / 20-bar avg)
    - Price distance from SMA20 (in standard deviations)
    - Multi-TF agreement score
    - Time of day (UTC hour / 24)
    - Strategy confidence
    """
    features = []

    strategy_onehot = {
        "MovingAverageCross": 0, "RSIMeanReversion": 1,
        "Breakout": 2, "BollingerReversion": 3, "VolumeSpike": 4,
    }
    features.append(float(strategy_onehot.get(signal.get("strategy", ""), 5)))

    features.append(float(market_data.get("rsi", 50)) / 100)
    features.append(float(market_data.get("atr_pct", 0.02)))
    features.append(float(market_data.get("volume_ratio", 1.0)))
    features.append(float(market_data.get("sma20_distance", 0.0)))
    features.append(float(market_data.get("mtf_agreement", 0)) / 4)
    features.append(float(market_data.get("hour", 12)) / 24)
    features.append(float(signal.get("confidence", 0.5)))

    # HMM regime probabilities (4 states) — always padded to fixed length so
    # training and prediction feature vectors stay aligned.
    hmm_probs = market_data.get("hmm_probs")
    if isinstance(hmm_probs, (list, tuple)) and len(hmm_probs) > 0:
        for p in hmm_probs[:4]:
            features.append(float(p))
        features.extend([0.0] * (4 - min(len(hmm_probs), 4)))
    else:
        features.extend([0.0] * 4)

    return np.array(features, dtype=np.float32)
