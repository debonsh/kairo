"""Meta-label retrainer — periodically retrains the meta-labeler on real outcomes.

The RandomForest is trained once at startup; markets drift, so it must be
retrained as real trades close. Features are recomputed from the candles just
before each entry (reusing build_meta_features), labels come from actual PnL.
"""

import numpy as np
from loguru import logger

from src.backtest.meta_labeling import build_meta_features

TF_MS = 900_000  # 15m


class MetaLabelRetrainer:
    def __init__(self, store, meta_labeler, min_trades: int = 30,
                 new_trades_before_retrain: int = 30,
                 min_trusted_samples: int = 100):
        self.store = store
        self.meta_labeler = meta_labeler
        self.min_trades = min_trades
        self.new_trades_before_retrain = new_trades_before_retrain
        self.min_trusted_samples = min_trusted_samples
        self.last_trained_count = 0

    def maybe_retrain(self, force: bool = False) -> dict:
        result = self.store.conn.execute(
            "SELECT COUNT(*) FROM trades WHERE status='closed' AND pnl IS NOT NULL"
        ).fetchone()
        total = int(result[0]) if result and result[0] else 0

        if not force and total - self.last_trained_count < self.new_trades_before_retrain:
            return {"trained": False, "reason": "not_enough_new_trades", "total": total}

        status = self.retrain()
        self.last_trained_count = total
        return status

    def retrain(self) -> dict:
        rows = self.store.conn.execute(
            """SELECT symbol, pnl, strategy, entry_time
               FROM trades WHERE status='closed' AND pnl IS NOT NULL
               ORDER BY entry_time DESC LIMIT 500"""
        ).fetchall()

        if len(rows) < self.min_trades:
            return {"trained": False, "reason": "insufficient_trades", "count": len(rows)}

        features, labels = [], []
        skipped = 0
        for sym, pnl, strat, ts in rows:
            f = self._features_from_entry(sym, ts, strat)
            if f is None:
                skipped += 1
                continue
            features.append(f)
            labels.append(1 if (pnl or 0) > 0 else 0)

        if len(features) < self.min_trades:
            return {"trained": False, "reason": "too_few_features", "count": len(features)}

        X = np.array(features, dtype=np.float32)
        y = np.array(labels, dtype=np.int64)
        self.meta_labeler.train(X, y)
        n = len(features)
        trusted = n >= self.min_trusted_samples
        # P0.4: sample-size caveat attached to every retrain — the same
        # discipline FuturesGate applies to itself before trusting stats.
        if not trusted:
            logger.warning(f"Meta-labeler retrained on {n}/{self.min_trusted_samples} "
                           f"live outcomes — predictions are advisory, not proof")
        return {
            "trained": self.meta_labeler.is_trained,
            "samples": n,
            "skipped": skipped,
            "positive_rate": round(float(y.mean()), 3),
            "trusted": trusted,
            "min_trusted_samples": self.min_trusted_samples,
            "caveat": None if trusted else (
                f"meta-model trained on only {n}/{self.min_trusted_samples} live "
                f"outcomes — treat its output as advisory"),
        }

    def _features_from_entry(self, symbol: str, ts_ms, strategy: str | None) -> np.ndarray | None:
        """Indicators from 15m candles just before the entry timestamp."""
        if not ts_ms:
            return None
        candles = self.store.get_candles(
            "bybit", symbol, "15m",
            start_ms=int(ts_ms) - 100 * TF_MS,
            end_ms=int(ts_ms),
        )
        if not candles or len(candles) < 30:
            return None

        closes = np.array([c["close"] for c in candles], dtype=float)
        highs = np.array([c["high"] for c in candles], dtype=float)
        lows = np.array([c["low"] for c in candles], dtype=float)
        volumes = np.array([c["volume"] for c in candles], dtype=float)

        rsi = self._rsi(closes[-15:])
        atr = float(np.mean(highs[-14:] - lows[-14:]))
        atr_pct = atr / closes[-1] if closes[-1] > 0 else 0.02
        sma20 = float(np.mean(closes[-20:]))
        std20 = float(np.std(closes[-20:])) if len(closes) >= 20 else 0
        sma20_dist = (closes[-1] - sma20) / std20 if std20 > 0 else 0.0
        vol_ratio = float(closes[-1] / np.mean(volumes[-20:])) if np.mean(volumes[-20:]) > 0 else 1.0
        hour = (int(ts_ms) // 3_600_000) % 24

        return build_meta_features(
            {"strategy": strategy or "ensemble", "confidence": 0.5},
            {
                "rsi": rsi,
                "atr_pct": atr_pct,
                "volume_ratio": vol_ratio,
                "sma20_distance": sma20_dist,
                "mtf_agreement": 0,
                "hour": hour,
                "hmm_probs": None,
            },
        )

    @staticmethod
    def _rsi(closes: np.ndarray, period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        deltas = np.diff(closes)
        gains = np.maximum(deltas, 0)
        losses = np.abs(np.minimum(deltas, 0))
        avg_gain = float(np.mean(gains[-period:])) if len(gains) >= period else 0
        avg_loss = float(np.mean(losses[-period:])) if len(losses) >= period else 0
        if avg_loss == 0:
            return 100.0
        return 100.0 - (100.0 / (1 + avg_gain / avg_loss))
