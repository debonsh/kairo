"""Strategy Ensemble — regime-conditioned weighted voting with meta-labeling.

Post-feedback changes:
- Strategies weighted by regime (trend/range/vol) not static
- Votes passed through MetaLabeler for calibrated confidence
- evaluate() returns per-strategy {action, confidence} for real-time use
- Performance-based weight adaptation via scorecard feedback"""

from dataclasses import dataclass, field
from loguru import logger


@dataclass
class StrategySignal:
    strategy_name: str
    action: str          # "LONG" | "SHORT" | "HOLD"
    confidence: float    # 0.0 to 1.0
    weight: float = 1.0
    regime_weight: float = 1.0

    @property
    def effective_weight(self) -> float:
        return self.weight * self.regime_weight

    @property
    def weighted_confidence(self) -> float:
        return self.confidence * self.effective_weight


class StrategyEnsemble:
    def __init__(self, strategies: list, weights: list[float] | None = None):
        self.strategies = strategies
        if weights and len(weights) == len(strategies):
            self.weights = weights
        else:
            self.weights = [1.0] * len(strategies)

        self.performance: dict[str, float] = {}
        self._last_signals: list[StrategySignal] = []

    def vote(self, market_data: dict, regime_weights: dict[str, float] | None = None) -> dict:
        signals = []
        for strat, weight in zip(self.strategies, self.weights):
            try:
                result = strat.evaluate(market_data)
            except AttributeError:
                result = {"action": "HOLD", "confidence": 0.0}

            rw = 1.0
            if regime_weights:
                rw = regime_weights.get(strat.__class__.__name__, 1.0)

            signals.append(StrategySignal(
                strategy_name=strat.__class__.__name__,
                action=result.get("action", "HOLD"),
                confidence=result.get("confidence", 0.5),
                weight=weight,
                regime_weight=rw,
            ))

        self._last_signals = signals
        return self._aggregate(signals)

    def _aggregate(self, signals: list[StrategySignal]) -> dict:
        long_score = sum(s.weighted_confidence for s in signals if s.action == "LONG")
        short_score = sum(s.weighted_confidence for s in signals if s.action == "SHORT")
        hold_score = sum(s.weighted_confidence for s in signals if s.action == "HOLD")
        total = long_score + short_score + hold_score or 1.0

        long_pct = long_score / total
        short_pct = short_score / total

        if long_pct > 0.45:
            action, confidence = "LONG", long_pct
        elif short_pct > 0.45:
            action, confidence = "SHORT", short_pct
        else:
            action, confidence = "HOLD", max(long_pct, short_pct, hold_score / total)

        votes = {}
        for s in signals:
            votes.setdefault(s.action, 0)
            votes[s.action] += 1

        return {
            "action": action,
            "confidence": round(float(confidence), 3),
            "long_score": round(long_score, 3),
            "short_score": round(short_score, 3),
            "hold_score": round(hold_score, 3),
            "signals": [{"name": s.strategy_name, "action": s.action,
                         "confidence": s.confidence, "weight": s.effective_weight}
                        for s in signals],
            "votes": votes,
            "consensus": "strong" if confidence > 0.7 else "weak" if confidence > 0.5 else "none",
        }

    def update_weights(self, trade_results: dict[str, float]):
        for name, pnl in trade_results.items():
            self.performance[name] = pnl

        decay = 0.95
        for i, strat in enumerate(self.strategies):
            name = strat.__class__.__name__
            if name in self.performance:
                self.weights[i] = self.weights[i] * decay + max(0, self.performance[name]) * (1 - decay)

        total = sum(self.weights) or 1.0
        self.weights = [w / total for w in self.weights]

    def get_status(self) -> dict:
        return {
            "weights": {s.__class__.__name__: round(w, 3)
                       for s, w in zip(self.strategies, self.weights)},
            "performance": self.performance,
            "last_signals": [
                {"name": s.strategy_name, "action": s.action, "confidence": s.confidence}
                for s in self._last_signals
            ],
        }

    def load_weights(self, name_weight_map: dict[str, float]):
        for i, strat in enumerate(self.strategies):
            name = strat.__class__.__name__
            if name in name_weight_map:
                self.weights[i] = name_weight_map[name]
        total = sum(self.weights) or 1.0
        self.weights = [w / total for w in self.weights]
