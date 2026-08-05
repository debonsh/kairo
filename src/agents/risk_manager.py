"""Risk Manager Agent — Half-Kelly + volatility-targeted position sizing.

Spec §2 (Aggressive Growth):
  f*        = max(0, (p·(b+1) − 1) / b)          # Kelly fraction
  b         = payout ratio = TP distance / SL distance
  p         = meta-labeler confidence (floored at meta_min_probability)
  f_alloc   = min(kelly_fraction · f*, max_position_pct)
  Vol_Adj   = (Capital × vol_target_risk_pct) / (ATR × sl_atr_multiplier)
  FinalSize = min(Vol_Adj, f_alloc × Capital, max_position_pct) × M_regime

All parameters are read per-tick via RuntimeStateManager.get_active_params(),
so a hot mode switch (vanilla ↔ aggressive) takes effect on the next trade
evaluation with zero restarts. The Gate still enforces absolute limits
downstream — this agent can VETO trades but cannot force them.
"""

from pathlib import Path

import yaml
from loguru import logger

from .llm_client import LLMClient
from src.config.state_manager import (
    micro_capital_effective_pct,
    conviction_multiplier,
    effective_position_pct,
)


class RiskManagerAgent:
    def __init__(self, llm: LLMClient, state_manager=None):
        self.llm = llm
        self.state = state_manager
        self.rules = self._load_rules()  # legacy fallback when no state manager
        self._vol_forecast: dict[str, float] = {}  # per-symbol EWMA ATR forecast
        self._vol_alpha = 0.3

    def _load_rules(self) -> dict:
        path = Path("config/risk_rules.yaml")
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f)
        return {}

    def _params(self) -> dict:
        """Active (deep-merged) parameters — fresh every evaluation tick."""
        if self.state is not None:
            return self.state.get_active_params()
        return self.rules

    def size_position(self, trade: dict, portfolio: dict, market_data: dict) -> dict:
        """Calculate position size: min(vol-adj, half-Kelly, max pct) × M_regime."""
        params = self._params()
        balance = portfolio.get("balance", 0)
        entry_price = trade.get("entry_price", 0)
        atr = self._extract_atr(market_data)

        if balance <= 0 or entry_price <= 0:
            return self._reject(trade, "Invalid balance or price")

        # Meta-labeler probability p (spec §2.1: p ≥ 0.55) — computed once and
        # shared by the Kelly engine and the conviction scaling.
        sizing = params.get("sizing", {})
        meta_floor = float(sizing.get("meta_min_probability", 0.55))
        meta_p = trade.get("meta_probability")
        if meta_p is None:
            meta_p = self._scorecard_win_rate(portfolio, trade.get("strategy", "unknown"))
        meta_p = min(max(float(meta_p), 0.0), 1.0)
        meta_p = max(meta_p, meta_floor)
        # Write the resolved p back so the Gate computes the SAME conviction
        # multiplier — otherwise (RF untrained + scorecard win-rate fallback)
        # the risk manager presses above a cap the gate doesn't see → blocked.
        trade["meta_probability"] = meta_p

        vol_adj = self._vol_adjusted_size(balance, atr, params, trade.get("symbol", "default"))
        kelly_units = self._half_kelly_size(trade, portfolio, params, entry_price, balance, meta_p)
        max_units = self._max_allowed_size(balance, entry_price, params)
        min_order = self._exchange_minimum(entry_price)

        # Micro accounts (balance below the scale-up threshold) skip the
        # vol-target constraint — their USD risk budget is sub-minimum anyway
        # (Kelly × micro-scaled max_pct stays ≤ the 1% risk target per trade)
        # and vol-targeting would otherwise pin size below the exchange min.
        micro = params.get("micro_capital") or {}
        micro_mode = bool(micro.get("enabled", True)) and balance < micro.get("balance_threshold", 2000)
        if micro_mode:
            candidates = [v for v in (kelly_units, max_units) if v > 0]
        else:
            candidates = [v for v in (vol_adj, kelly_units, max_units) if v > 0]
        size = min(candidates) if candidates else 0.0
        size = max(size, 0.0)

        # Meta-confidence scaling (spec: statistical conviction).
        conv = conviction_multiplier(meta_p, params)

        # Regime multiplier M_regime — press winners (scales ABOVE the base
        # cap, matching the gate), shrink into chop/panic.
        regime = trade.get("regime", "unknown")
        regime_mult = float((params.get("regime_multipliers") or {}).get(regime, 1.0))

        size *= conv
        size *= regime_mult

        # De-risking / disagreement multipliers (sharpe drift, agent disagreement).
        size *= float(trade.get("risk_multiplier", 1.0))

        # OI divergence = rally not backed by new money → size down.
        if trade.get("oi_diverging"):
            size *= 0.75

        # Pressed cap — base cap × conviction × max(M_regime, 1). Identical to
        # the Gate's effective_position_pct, so sizing never gate-blocks.
        pressed_cap = max_units * conv * max(regime_mult, 1.0)
        size = min(size, pressed_cap)

        if size * entry_price < min_order:
            return self._reject(trade, f"Size ${size * entry_price:.2f} below exchange minimum ${min_order}")

        size = round(size, 8)
        usdt_value = size * entry_price

        trade["quantity"] = size
        trade["usdt_value"] = usdt_value
        trade["sizing_method"] = {
            "vol_targeted": round(vol_adj * entry_price, 2),
            "kelly": round(kelly_units * entry_price, 2),
            "max_allowed": round(max_units * entry_price, 2),
            "regime": regime,
            "m_regime": round(regime_mult, 2),
            "conviction": round(conv, 3),
            "p": round(meta_p, 3),
            "pressed_cap": round(pressed_cap * entry_price, 2),
            "final": round(usdt_value, 2),
            "atr": round(atr, 6),
        }

        return {"decision": "SIZED", "trade": trade, "size_usdt": usdt_value, "size_units": size}

    def validate(self, trade: dict, portfolio: dict) -> dict:
        hard_check = self._hard_rule_check(trade, portfolio)
        if not hard_check["passed"]:
            return {"decision": "REJECTED", "reason": hard_check["reason"],
                    "check": hard_check, "source": "hard_rules"}

        llm_check = self._llm_validation(trade, portfolio)
        return {
            "decision": "APPROVE",
            "reason": llm_check.get("reason", "LLM advisory — gate enforces final rules"),
            "hard_check": hard_check,
            "llm_check": llm_check,
            "source": "risk_manager",
        }

    # ------------------------------------------------------------------ #
    # Spec §2.2 — volatility-targeted size
    # ------------------------------------------------------------------ #
    def _vol_adjusted_size(self, balance: float, atr: float, params: dict,
                           symbol: str = "default") -> float:
        """Vol_Adj = (Capital × Target_Risk) / (ATR_forecast × SL_Multiplier).

        Maintains a constant risk budget across regimes: wider ATR or a wider
        stop (larger SL multiplier) ⇒ smaller position, and vice-versa. Uses an
        EWMA-smoothed ATR forecast (GARCH-lite) so we don't size up into a
        fresh volatility spike.
        """
        sizing = params.get("sizing", {})
        risk_pct = float(sizing.get("vol_target_risk_pct", 0.01))
        sl_mult = float(sizing.get("sl_atr_multiplier", 2.0))
        atr_eff = self._forecast_atr(symbol, atr)
        denominator = max(atr_eff * sl_mult, 1e-9)
        return (balance * risk_pct) / denominator

    def _forecast_atr(self, symbol: str, atr: float) -> float:
        """Per-symbol EWMA-smoothed ATR forecast (reacts faster than raw ATR)."""
        if symbol not in self._vol_forecast:
            self._vol_forecast[symbol] = atr
        else:
            prev = self._vol_forecast[symbol]
            self._vol_forecast[symbol] = self._vol_alpha * atr + (1 - self._vol_alpha) * prev
        return self._vol_forecast[symbol]

    # ------------------------------------------------------------------ #
    # Spec §2.1 — Half-Kelly size
    # ------------------------------------------------------------------ #
    def _half_kelly_size(self, trade: dict, portfolio: dict, params: dict,
                         entry_price: float, balance: float, p: float) -> float:
        """f* = max(0, (p·(b+1) − 1)/b); f_alloc = min(kelly_fraction·f*, max_pct)."""
        sizing = params.get("sizing", {})
        pre_trade = params.get("pre_trade", {})
        kelly_fraction = float(sizing.get("kelly_fraction", 0.25))
        # Kelly cap respects micro-capital scale-up so small accounts can
        # actually size above the exchange minimum (matches the gate).
        base_max_pct = float(pre_trade.get("max_position_pct", 2.0))
        min_order = self._exchange_minimum(entry_price)
        max_pct = micro_capital_effective_pct(balance, base_max_pct, params, min_order) / 100.0

        # Payout ratio b = TP distance / SL distance (from the actual proposal).
        b = self._payout_ratio(trade, sizing)
        if b <= 0:
            return 0.0

        f_star = max(0.0, (p * (b + 1.0) - 1.0) / b)
        f_alloc = min(kelly_fraction * f_star, max_pct)

        if entry_price <= 0:
            return float("inf") if f_alloc > 0 else 0.0

        return (balance * f_alloc) / entry_price

    @staticmethod
    def _payout_ratio(trade: dict, sizing: dict) -> float:
        """b = TP distance / SL distance. Falls back to profile multipliers."""
        entry = trade.get("entry_price", 0)
        sl = trade.get("stop_loss", 0)
        tp = trade.get("take_profit", 0)
        action = str(trade.get("action", "LONG")).upper()

        if entry and sl and tp and sl != entry:
            if action == "SHORT":
                tp_dist = entry - tp
                sl_dist = sl - entry
            else:
                tp_dist = tp - entry
                sl_dist = entry - sl
            if sl_dist > 0 and tp_dist > 0:
                return tp_dist / sl_dist

        sl_mult = float(sizing.get("sl_atr_multiplier", 2.0))
        tp_mult = float(sizing.get("tp_atr_multiplier", 4.0))
        return tp_mult / sl_mult if sl_mult > 0 else 0.0

    @staticmethod
    def _scorecard_win_rate(portfolio: dict, agent: str) -> float:
        stats = (portfolio.get("scorecard") or {}).get(agent, {})
        if stats and stats.get("total", 0) >= 10:
            return max(0.0, min(1.0, stats.get("accuracy", 50) / 100.0))
        return 0.55  # no track record yet → spec floor

    # ------------------------------------------------------------------ #
    # Caps & helpers
    # ------------------------------------------------------------------ #
    def _max_allowed_size(self, balance: float, entry_price: float, params: dict) -> float:
        pre_trade = params.get("pre_trade", {})
        base_pct = pre_trade.get("max_position_pct", 2.0)
        min_order = self._exchange_minimum(entry_price)
        max_pct = micro_capital_effective_pct(balance, base_pct, params, min_order)
        return balance * max_pct / 100 / entry_price if entry_price > 0 else 0

    def _exchange_minimum(self, entry_price: float) -> float:
        return max(5.0, entry_price * 0.0001)

    def _extract_atr(self, market_data: dict) -> float:
        for tf in ["15m", "1h"]:
            if tf in market_data and isinstance(market_data[tf], dict):
                atr = market_data[tf].get("atr", 0)
                if atr > 0:
                    return atr
        return 0.01

    def _reject(self, trade: dict, reason: str) -> dict:
        return {"decision": "REJECTED", "reason": reason, "trade": trade,
                "size_usdt": 0, "size_units": 0}

    # ------------------------------------------------------------------ #
    # Hard rule checks (enforced here + again at the Gate)
    # ------------------------------------------------------------------ #
    def _hard_rule_check(self, trade: dict, portfolio: dict) -> dict:
        params = self._params()
        pre_trade = params.get("pre_trade", {})
        position = params.get("position", {})

        balance = portfolio.get("balance", 0)
        positions = portfolio.get("open_positions", 0)
        if isinstance(positions, int):
            num_positions = positions
        else:
            num_positions = len(positions) if hasattr(positions, '__len__') else 0

        base_max_pct = pre_trade.get("max_position_pct", 2.0)
        # Sanity cap (2×) uses the FULL effective pct — micro scale-up ×
        # conviction × regime pressing — so pressed trades aren't false-rejected.
        max_pct = effective_position_pct(balance, base_max_pct, params,
                                         trade.get("regime", "unknown"),
                                         trade.get("meta_probability"))

        trade_value = trade.get("usdt_value", trade.get("size_usdt", 0))
        if balance > 0 and trade_value / balance * 100 > max_pct * 2:
            return {"passed": False, "reason": f"Position {trade_value/balance*100:.1f}% exceeds max {max_pct * 2}%"}

        max_positions = position.get("max_positions_total", 5)
        if num_positions >= max_positions:
            return {"passed": False, "reason": f"Max positions {max_positions} reached"}

        sl = trade.get("stop_loss_pct", trade.get("stop_loss", 0))
        tp = trade.get("take_profit_pct", trade.get("take_profit", 0))
        if isinstance(sl, (int, float)) and isinstance(tp, (int, float)) and sl > 0 and tp > 0:
            min_rr = pre_trade.get("min_risk_reward_ratio", 1.5)
            if tp / sl < min_rr:
                return {"passed": False, "reason": f"R:R ratio {tp/sl:.1f} below minimum {min_rr}"}

        return {"passed": True, "reason": "Hard rules passed",
                "checks_performed": ["position_size", "max_positions", "rr_ratio"]}

    def _llm_validation(self, trade: dict, portfolio: dict) -> dict:
        prompt_path = Path("config/prompts/risk_manager.txt")
        if not prompt_path.exists():
            return {"approved": True, "reason": "No risk prompt template"}

        template = prompt_path.read_text()
        prompt = (template
                  .replace("{{trade_proposal}}", str(trade))
                  .replace("{{portfolio}}", str(portfolio))
                  .replace("{{risk_rules}}", str(self._params())))

        try:
            response = self.llm.ask(prompt, temperature=0.2, max_tokens=256)
        except Exception as e:
            logger.warning(f"Risk LLM failed: {e} — defaulting to approve")
            return {"approved": True, "reason": f"LLM unavailable: {e}"}

        text = response.text or ""
        if not text.strip():
            # Empty response — default to approve (gate enforces real limits).
            return {"approved": True, "reason": "Empty LLM response — defaulting to approve", "risk_score": 5}

        return {
            "approved": "APPROVE" in text.upper()[:50],
            "reason": text[:200],
            "risk_score": 5,
        }

    def daily_check(self, portfolio: dict) -> dict:
        params = self._params()
        account_rules = params.get("account", {})
        max_daily_loss = account_rules.get("max_daily_loss_pct", 5.0)
        max_drawdown = account_rules.get("max_total_drawdown_pct", 10.0)

        daily_pnl = portfolio.get("daily_pnl_pct", 0)
        drawdown = portfolio.get("drawdown_pct", 0)

        limits_hit = []
        if daily_pnl <= -max_daily_loss:
            limits_hit.append(f"Daily loss: {daily_pnl}% (max {max_daily_loss}%)")
        if drawdown >= max_drawdown:
            limits_hit.append(f"Drawdown: {drawdown}% (max {max_drawdown}%)")

        return {
            "trading_allowed": len(limits_hit) == 0,
            "limits_hit": limits_hit,
            "daily_pnl_pct": daily_pnl,
            "drawdown_pct": drawdown,
        }
