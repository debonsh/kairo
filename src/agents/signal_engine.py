"""Signal Engine — real-time strategy ensemble with meta-labeling filter.
Replaces the Strategist agent's signal origination role. Produces
deterministic, backtest-validated trade proposals that the LLM can
only VETO, never force."""

import numpy as np
from loguru import logger

from src.backtest.regime_detector import RegimeDetector, RegimeResult
from src.backtest.meta_labeling import MetaLabelClassifier, build_meta_features


class SignalEngine:
    def __init__(self, meta_labeler: MetaLabelClassifier | None = None,
                 state_manager=None):
        self.meta_labeler = meta_labeler
        self.state_manager = state_manager
        self.regime_detector = RegimeDetector()

        self.strategies = {}

    def _params(self) -> dict:
        """Active profile params — read fresh every evaluation tick."""
        if self.state_manager is not None:
            return self.state_manager.get_active_params()
        return {}

    def evaluate(self, market_data: dict[str, dict], symbol: str,
                 sentiment_bias: dict | None = None) -> dict:
        """Evaluate all strategies on current market data, produce consensus.

        Returns: {action: "LONG"|"SHORT"|"HOLD", confidence: float,
                  signals: [...], regime: dict, meta: dict, llm_veto_allowed: bool}

        Enforces a confidence floor (default 0.55, profile-tunable) — signals
        below the floor are downgraded to HOLD.
        """
        params = self._params()
        pre_trade = params.get("pre_trade", {})
        regime_cfg = params.get("regime", {})
        regime_result = self.regime_detector.detect(
            market_data, symbol,
            multipliers=params.get("regime_multipliers"),
            adx_threshold=regime_cfg.get("adx_trend_threshold"),
            vol_threshold=regime_cfg.get("vol_percentile_threshold"),
        )
        regime_weights = regime_result.weights

        signals = []
        for name, strategy_class in self.strategies.items():
            try:
                result = strategy_class.evaluate(market_data)
                result["strategy"] = name
                result["regime_weight"] = regime_weights.get(name, 1.0)
                signals.append(result)
            except Exception as e:
                logger.debug(f"Strategy {name} evaluate failed: {e}")

        if not signals:
            return self._hold_result(regime_result)

        long_score = 0.0
        short_score = 0.0
        hold_score = 0.0

        for s in signals:
            w = s.get("regime_weight", 1.0)
            conf = s.get("confidence", 0.5)
            weighted = w * conf

            if s["action"] == "LONG":
                long_score += weighted
            elif s["action"] == "SHORT":
                short_score += weighted
            else:
                hold_score += weighted

        total = long_score + short_score + hold_score
        if total == 0:
            return self._hold_result(regime_result)

        long_pct = long_score / total
        short_pct = short_score / total

        if long_pct > 0.45:
            action, confidence = "LONG", long_pct
        elif short_pct > 0.45:
            action, confidence = "SHORT", short_pct
        else:
            return self._hold_result(regime_result)

        # 0.55 confidence threshold floor (profile-tunable) — high-conviction
        # entries only. Below the floor the signal is not actionable.
        min_confidence = float(pre_trade.get("min_confidence", 0.55))
        if confidence < min_confidence:
            logger.debug(f"{symbol}: confidence {confidence:.2f} < floor {min_confidence} — HOLD")
            return self._hold_result(regime_result)

        meta_result = {"signal_valid": True, "confidence": float(confidence), "reason": "no_meta_model"}

        if self.meta_labeler and self.meta_labeler.is_trained and action != "HOLD":
            flat = self._flatten_market(market_data)
            if regime_result.hmm_probs:
                flat["hmm_probs"] = regime_result.hmm_probs
            features = build_meta_features(
                {"strategy": signals[0].get("strategy", ""), "confidence": confidence,
                 "action": action},
                flat,
            )
            meta_result = self.meta_labeler.predict(features)
            if not meta_result["signal_valid"]:
                confidence *= 0.3
            # P0.4: sample-size caveat rides along with the meta verdict so
            # downstream consumers (strategist prompt, sizing, dashboard) know
            # whether the RF was trained on enough live outcomes to trust.
            if not meta_result.get("trusted", False) and meta_result.get("sample_size", 0) > 0:
                logger.debug(f"{symbol}: {meta_result.get('caveat', 'low-sample meta model')}")

        return {
            "action": action,
            "confidence": round(min(confidence, 0.95), 3),
            "signals": signals,
            "regime": {
                "regime": regime_result.regime.value,
                "adx": regime_result.adx,
                "realized_vol": regime_result.realized_vol,
                "hurst": regime_result.hurst,
                "weights": regime_result.weights,
                "hmm_probs": regime_result.hmm_probs,
                "hmm": regime_result.hmm,
                "m_regime": regime_result.m_regime,
            },
            "meta": meta_result,
            "llm_veto_allowed": True,
            "source": "signal_engine",
        }

    def _hold_result(self, regime_result: RegimeResult) -> dict:
        return {
            "action": "HOLD",
            "confidence": 0.0,
            "signals": [],
            "regime": {
                "regime": regime_result.regime.value,
                "adx": regime_result.adx,
                "realized_vol": regime_result.realized_vol,
                "hurst": regime_result.hurst,
            },
            "meta": {"signal_valid": False, "reason": "no_consensus"},
            "llm_veto_allowed": False,
            "source": "signal_engine",
        }

    def _flatten_market(self, market_data: dict[str, dict]) -> dict:
        flat = {}
        for tf_data in market_data.values():
            if isinstance(tf_data, dict):
                flat.update(tf_data)
        return flat

    def register_strategies(self, strategy_classes: list):
        for cls in strategy_classes:
            self.strategies[cls.__name__] = cls
        logger.info(f"SignalEngine registered {len(self.strategies)} strategies")
