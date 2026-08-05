"""Agent Orchestrator — coordinates the deterministic-first trading pipeline.

New flow (post-feedback):
  Raw Data → SignalEngine (deterministic) → MetaLabeler filter
  → LLM Strategist (can VETO, cannot force)
  → RiskManager (vol-targeted + Kelly sizing)
  → Gate (absolute rules, schema validation)
  → Disagreement check → Execute

Agent disagreement is a risk signal — if Analyst and Strategist diverge
substantially, size down or skip entirely."""

import time
import uuid
from datetime import datetime
from loguru import logger

from .llm_client import LLMClient
from .analyst import AnalystAgent
from .sentiment import SentimentAgent
from .strategist import StrategistAgent
from .risk_manager import RiskManagerAgent
from .gate import ValidationGate
from .signal_engine import SignalEngine
from .social_sentiment import SocialSentimentAgent
from .derivatives import DerivativesAgent
from ..learning.memory import DecisionMemory
from ..config.state_manager import get_dedup_key
from .joint_sizer import JointPositionSizer


class AgentOrchestrator:
    def __init__(self, llm: LLMClient, store, signal_engine: SignalEngine,
                 state_manager=None):
        self.llm = llm
        self.store = store
        self.state_manager = state_manager

        self.signal_engine = signal_engine
        self.analyst = AnalystAgent(llm)
        self.sentiment = SentimentAgent(llm)
        self.strategist = StrategistAgent(llm)
        self.risk_manager = RiskManagerAgent(llm, state_manager)
        self.gate = ValidationGate(state_manager)
        self.memory = DecisionMemory(store)
        self.derivatives = DerivativesAgent()
        self.social = SocialSentimentAgent(llm, store)
        self.joint_sizer = JointPositionSizer(store)

        self.cycle_count = 0
        self.start_time = datetime.now()
        self.sharpe_risk_multiplier = 1.0

        # LLM verdict cache: dedup within same cycle
        self._llm_cache: dict[str, dict] = {}
        self._cycle_market_cache: dict[str, dict] = {}

    def run_cycle(self, symbol: str, market_data: dict, portfolio: dict) -> dict:
        self._llm_cache = {}  # fresh per cycle
        self.cycle_count += 1
        cycle_id = str(uuid.uuid4())[:8]
        t0 = time.time()

        signal = self.signal_engine.evaluate(market_data, symbol)
        logger.debug(f"[{cycle_id}] SignalEngine: {signal['action']} conf={signal['confidence']:.2f} "
                    f"regime={signal.get('regime', {}).get('regime', '?')}")

        if signal["action"] == "HOLD":
            latency = int((time.time() - t0) * 1000)
            return self._build_result(cycle_id, signal, signal["confidence"], None, latency)

        analysis = self.analyst.analyze(market_data, symbol)
        sentiment_data = self.sentiment.gather_sync(symbol)
        sentiment_bias = self.sentiment.get_trading_bias(sentiment_data)

        analysis["sentiment"] = sentiment_bias
        analysis["current_price"] = self._extract_price(market_data)

        derivatives_ctx = self.derivatives.get_context(symbol)
        analysis["derivatives"] = derivatives_ctx

        memory_context = self.memory.get_memory_context(symbol, limit=10)

        social_ctx = self.social.get_context_for_llm(symbol)
        if social_ctx:
            memory_context = social_ctx + "\n\n" + memory_context

        # LLM verdict cache: same coin+action+regime combo in this cycle → reuse
        signal_id = signal.get("action", "?") + signal.get("regime", {}).get("regime", "?") + symbol
        cached = self._llm_cache.get(signal_id)
        if cached:
            filter_result = cached
            logger.debug(f"[{cycle_id}] Reused cached LLM verdict for {signal_id}")
        else:
            filter_result = self.strategist.filter(signal, analysis, sentiment_data, portfolio, symbol,
                                                   memory=memory_context)
            self._llm_cache[signal_id] = filter_result
            logger.debug(f"[{cycle_id}] Strategist filter: {filter_result['filter_action']}")

        if filter_result["filter_action"] == "REJECT":
            latency = int((time.time() - t0) * 1000)
            return self._build_result(cycle_id, signal, filter_result["confidence"], filter_result, latency)

        disagreement = self._measure_disagreement(signal, filter_result)
        if disagreement["action"] == "SKIP":
            logger.info(f"[{cycle_id}] Disagreement skip: {disagreement['reason']}")
            latency = int((time.time() - t0) * 1000)
            return self._build_result(cycle_id, signal, 0, filter_result, latency)

        trade_proposal = self._build_proposal(signal, analysis, disagreement, symbol, market_data, derivatives_ctx)
        risk_result = self.risk_manager.validate(trade_proposal, portfolio)

        if risk_result["decision"] != "APPROVE":
            logger.info(f"[{cycle_id}] REJECTED by risk: {risk_result.get('reason', '?')}")
            latency = int((time.time() - t0) * 1000)
            return self._build_result(cycle_id, signal, signal["confidence"], filter_result, latency)

        sized = self.risk_manager.size_position(trade_proposal, portfolio, market_data)
        if sized["decision"] != "SIZED":
            logger.info(f"[{cycle_id}] Sizing failed: {sized['reason']}")
            latency = int((time.time() - t0) * 1000)
            return self._build_result(cycle_id, signal, signal["confidence"], filter_result, latency)

        # P2.1: joint position sizing — re-allocate the candidate's notional
        # against open positions' correlation. Falls back to per-signal size
        # when cvxpy/correlation data unavailable; never raises above caps.
        final_trade = sized["trade"]
        if self.joint_sizer.available():
            try:
                joint = self.joint_sizer.size_with_open(
                    final_trade, portfolio.get("open_trades", []), portfolio,
                    market_data, sized.get("size_usdt", final_trade.get("usdt_value", 0)),
                )
                if joint.get("joint"):
                    adj = joint["adjusted_usdt"]
                    if adj > 0 and final_trade.get("entry_price", 0) > 0:
                        final_trade["quantity"] = round(adj / final_trade["entry_price"], 8)
                        final_trade["usdt_value"] = round(adj, 2)
                    final_trade["joint_sizing"] = {
                        "adjusted_usdt": joint["adjusted_usdt"],
                        "weights": joint.get("weights"),
                        "portfolio_risk": joint.get("portfolio_risk"),
                    }
                    logger.debug(f"[{cycle_id}] Joint sizing: {joint['symbols']} "
                                 f"risk={joint.get('portfolio_risk')}")
            except Exception as e:
                logger.debug(f"[{cycle_id}] Joint sizing skipped: {e}")

        gate_result = self.gate.validate(final_trade, portfolio, analysis, sentiment_data, derivatives_ctx)

        if not gate_result["passed"]:
            logger.info(f"[{cycle_id}] BLOCKED by gate: {gate_result['reason']}")
            latency = int((time.time() - t0) * 1000)
            return self._build_result(cycle_id, signal, signal["confidence"], filter_result, latency)

        latency = int((time.time() - t0) * 1000)

        log_entry = {
            "cycle_id": cycle_id,
            "signal": signal,
            "analysis": analysis,
            "filter": filter_result,
            "sizing": sized.get("sizing_method"),
            "gate": gate_result,
            "latency_ms": latency,
        }
        self.store.log_agent_decision(cycle_id, symbol, "orchestrator", log_entry, latency_ms=latency)

        return self._build_result(cycle_id, signal, signal["confidence"], filter_result, latency,
                                  executable=True, trade=final_trade)

    def _build_proposal(self, signal: dict, analysis: dict,
                        disagreement: dict, symbol: str,
                        market_data: dict | None = None,
                        derivatives: dict | None = None) -> dict:
        params = self.state_manager.get_active_params() if self.state_manager else {}
        pre_trade = params.get("pre_trade", {})
        sizing = params.get("sizing", {})

        price = analysis.get("current_price", 0)
        size_mult = disagreement.get("size_multiplier", 1.0)
        volatility = self._extract_volatility(market_data or {})

        meta = signal.get("meta") or {}
        meta_reason = meta.get("reason", "")
        meta_trained = "RF confidence" in meta_reason
        # None (not 1.0) when untrained — lets the Kelly engine pick its own p.
        meta_probability = float(meta.get("confidence", 0.5)) if meta_trained else None
        strategy = (signal.get("signals") or [{}])[0].get("strategy", "ensemble")
        # OI divergence only matters for trend trades — a falling-OI rally is a
        # weak short-covering move. Mean-reversion entries don't need OI confirmation.
        oi_diverging = bool(derivatives and derivatives.get("ok")
                            and derivatives.get("oi_delta_pct") is not None
                            and derivatives.get("oi_delta_pct") < 0
                            and strategy in ("MovingAverageCross", "Breakout"))

        # ATR-scaled SL/TP (spec §3.1 asymmetric barriers):
        #   SL = max(sl_atr_multiplier × ATR%, min_sl_pct)
        #   TP = max(tp_atr_multiplier × ATR%, min_tp_pct, SL × min_rr)
        # The min floors preserve vanilla behavior (fixed 1.5%/3%) on quiet
        # coins while aggressive keeps tight ATR-relative stops (1×/3×).
        atr_pct = self._extract_atr_pct(market_data)
        sl_mult = float(sizing.get("sl_atr_multiplier", 2.0))
        tp_mult = float(sizing.get("tp_atr_multiplier", 4.0))
        min_rr = float(pre_trade.get("min_risk_reward_ratio", 1.5))
        min_sl_pct = float(sizing.get("min_sl_pct", 0.015))
        min_tp_pct = float(sizing.get("min_tp_pct", 0.03))
        base_sl_pct = max(atr_pct * sl_mult, min_sl_pct)
        base_tp_pct = max(atr_pct * tp_mult, base_sl_pct * min_rr, min_tp_pct)

        if signal["action"] == "LONG":
            sl = price * (1 - base_sl_pct)
            tp = price * (1 + base_tp_pct)
        else:
            sl = price * (1 + base_sl_pct)
            tp = price * (1 - base_tp_pct)

        return {
            "action": signal["action"],
            "symbol": symbol,
            "entry_price": price,
            "stop_loss": sl,
            "take_profit": tp,
            "stop_loss_pct": base_sl_pct,
            "take_profit_pct": base_tp_pct,
            "size_usdt": 20.0 * size_mult * self.sharpe_risk_multiplier,
            "risk_multiplier": size_mult * self.sharpe_risk_multiplier,
            "confidence": signal["confidence"],
            "strategy": strategy,
            "regime": signal.get("regime", {}).get("regime", "unknown"),
            "volatility_15m": volatility,
            "meta_probability": meta_probability,
            "oi_diverging": oi_diverging,
        }

    def _measure_disagreement(self, signal: dict, filter_result: dict) -> dict:
        signal_conf = signal.get("confidence", 0.5)
        filter_conf = filter_result.get("confidence", 0.5)

        agreement = 1.0 - abs(signal_conf - filter_conf)

        if agreement < 0.3:
            return {"action": "SKIP", "size_multiplier": 0.0,
                    "reason": f"Strong disagreement: signal={signal_conf:.2f} filter={filter_conf:.2f}"}
        elif agreement < 0.5:
            return {"action": "SIZE_DOWN", "size_multiplier": 0.5,
                    "reason": f"Moderate disagreement: signal={signal_conf:.2f} filter={filter_conf:.2f}"}
        else:
            return {"action": "PROCEED", "size_multiplier": 1.0,
                    "reason": f"Agreement: {agreement:.2f}"}

    def _build_result(self, cycle_id: str, signal: dict, confidence: float,
                      filter_result: dict | None, latency_ms: int,
                      executable: bool = False, trade: dict | None = None) -> dict:
        return {
            "cycle_id": cycle_id,
            "timestamp": datetime.now().isoformat(),
            "action": signal["action"],
            "confidence": confidence,
            "executable": executable,
            "trade": trade,
            "latency_ms": latency_ms,
        }

    def _extract_price(self, market_data: dict) -> float:
        for tf in ["15m", "1h", "4h", "1d"]:
            if tf in market_data and isinstance(market_data[tf], dict):
                price = market_data[tf].get("close")
                if price:
                    return price
        return 0.0

    def _extract_volatility(self, market_data: dict) -> float:
        """Highest 15m volatility across timeframes, for the gate's volatility check."""
        vols = [
            tf_data.get("volatility_15m", 0)
            for tf_data in market_data.values()
            if isinstance(tf_data, dict)
        ]
        return max(vols) if vols else 0.0

    def _extract_atr_pct(self, market_data: dict) -> float:
        """ATR as % of price from the fastest timeframe (15m preferred)."""
        for tf in ["15m", "1h"]:
            tf_data = market_data.get(tf)
            if isinstance(tf_data, dict):
                atr_pct = tf_data.get("atr_pct", 0)
                if atr_pct and atr_pct > 0:
                    return float(atr_pct)
        return 0.0075

    def get_status(self) -> dict:
        uptime = datetime.now() - self.start_time
        joint = {}
        try:
            joint = self.joint_sizer.get_status()
        except Exception:
            pass
        llm_provider = None
        try:
            llm_provider = getattr(self.llm, "provider", None)
        except Exception:
            pass
        return {
            "cycles_completed": self.cycle_count,
            "uptime_hours": round(uptime.total_seconds() / 3600, 1),
            "sharpe_risk_multiplier": round(self.sharpe_risk_multiplier, 3),
            "joint_sizer": joint,
            "llm": llm_provider,
        }

    def apply_sharpe_multiplier(self, multiplier: float):
        self.sharpe_risk_multiplier = max(0.1, min(1.0, multiplier))

    def compute_live_sharpe(self) -> float:
        rows = self.store.conn.execute(
            "SELECT pnl FROM trades WHERE status='closed' AND pnl IS NOT NULL ORDER BY exit_time DESC LIMIT 100"
        ).fetchall()
        if len(rows) < 5:
            return 0.0
        pnls = [float(r[0]) for r in rows if r[0] is not None]
        if len(pnls) < 5:
            return 0.0
        returns = [p / 5000.0 for p in pnls]
        avg = sum(returns) / len(returns)
        variance = sum((r - avg) ** 2 for r in returns) / len(returns)
        if variance <= 0:
            return 0.0
        std = variance ** 0.5
        return avg / std * (252 ** 0.5) if std > 0 else 0.0
