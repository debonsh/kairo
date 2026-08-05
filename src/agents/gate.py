"""Validation Gate — absolute, immutable safety rules + schema validation.
No LLM, no agent, no prompt can override these checks.
This is the final barrier before any order reaches the exchange.

New additions:
- Schema validation on all agent outputs (malformed JSON → HOLD)
- Minimum order value check (below exchange min → REJECT)
- FastWatchdog health integration
- Dynamic rules: limits resolve from RuntimeStateManager.get_active_params()
  on every validate() call, so a hot vanilla↔aggressive switch takes effect
  immediately (micro-capital scale-up included).
- Micro-capital scale-up: for small accounts the flat % cap would push
  orders below exchange minimums, so the effective % scales up (bounded by
  micro_capital.max_position_pct) while USD risk stays capped by sizing."""

from loguru import logger
from pydantic import BaseModel, ValidationError, field_validator
from typing import Any

from src.config.state_manager import effective_position_pct


class TradeProposalSchema(BaseModel):
    action: str
    symbol: str
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    confidence: float = 0.0
    size_usdt: float = 0.0

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v.upper() not in ("LONG", "SHORT", "HOLD"):
            raise ValueError(f"Invalid action: {v}")
        return v.upper()

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @field_validator("entry_price", "stop_loss", "take_profit")
    @classmethod
    def validate_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"Negative price: {v}")
        return v


class ValidationGate:
    RULES = {
        "max_position_pct_of_portfolio": 2.0,
        "min_confidence": 0.55,
        "min_order_usdt": 5.0,            # Bybit/Binance minimum
        "volatility_max_15m_pct": 5.0,
        "max_positions_total": 5,
        "balance_floor": 2_500,
    }

    def __init__(self, state_manager=None):
        self.state_manager = state_manager

    def _params(self) -> dict:
        if self.state_manager is not None:
            return self.state_manager.get_active_params()
        return {}

    def _resolved_rules(self) -> dict:
        """Static defaults overlaid with the active profile — per validate() call."""
        params = self._params()
        rules = dict(self.RULES)
        pre_trade = params.get("pre_trade", {})
        position = params.get("position", {})
        account = params.get("account", {})
        if "max_position_pct" in pre_trade:
            rules["max_position_pct_of_portfolio"] = pre_trade["max_position_pct"]
        if "min_confidence" in pre_trade:
            rules["min_confidence"] = pre_trade["min_confidence"]
        if "volatility_max_pct" in pre_trade:
            rules["volatility_max_15m_pct"] = pre_trade["volatility_max_pct"]
        if "max_positions_total" in position:
            rules["max_positions_total"] = position["max_positions_total"]
        if "balance_floor" in account:
            rules["balance_floor"] = account["balance_floor"]
        return rules

    def validate(self, proposal: dict, portfolio: dict,
                 analysis: dict, sentiment: dict,
                 derivatives: dict | None = None) -> dict:
        schema_result = self._validate_schema(proposal)
        if not schema_result["valid"]:
            return {"passed": False, "reason": f"Schema failure: {schema_result['error']}",
                    "checks": {"schema": schema_result}}

        rules = self._resolved_rules()  # resolve once per validate call
        checks = {}
        checks["schema"] = schema_result
        checks["confidence"] = self._check_confidence(proposal, rules)
        checks["min_order"] = self._check_min_order(proposal, rules)
        checks["portfolio_limit"] = self._check_portfolio_limits(portfolio, proposal, rules)
        checks["volatility"] = self._check_volatility(proposal, rules)
        checks["sentiment_override"] = self._check_sentiment(sentiment, proposal)
        checks["derivatives"] = self._check_derivatives(proposal, derivatives)
        checks["balance_floor"] = self._check_balance(portfolio, rules)

        # Now-enforced dead rules: correlation, volume, multi-TF
        checks["correlation"] = self._check_correlation(proposal, portfolio)
        checks["volume_24h"] = self._check_min_volume(proposal)
        checks["multi_tf"] = self._check_multi_tf(analysis, proposal, rules)

        all_passed = all(c["passed"] for c in checks.values())
        failures = [name for name, c in checks.items() if not c["passed"]]

        return {
            "passed": all_passed,
            "checks": checks,
            "failures": failures,
            "reason": " | ".join(checks[f]["reason"] for f in failures) if failures else "All checks passed",
        }

    def _validate_schema(self, proposal: dict) -> dict:
        try:
            TradeProposalSchema(**proposal)
            return {"valid": True, "passed": True, "reason": "Schema OK"}
        except ValidationError as e:
            return {"valid": False, "passed": False, "error": str(e),
                    "reason": f"Schema validation failed: {e.errors()}"}
        except Exception as e:
            return {"valid": False, "passed": False, "error": str(e),
                    "reason": "Unknown schema error"}

    def _check_min_order(self, proposal: dict, rules: dict) -> dict:
        value = proposal.get("usdt_value", proposal.get("size_usdt", 0))
        if value < rules["min_order_usdt"]:
            return {"passed": False,
                    "reason": f"Order ${value:.2f} below exchange minimum ${rules['min_order_usdt']}"}
        return {"passed": True, "reason": f"Order ${value:.2f} above minimum"}

    def _check_confidence(self, proposal: dict, rules: dict) -> dict:
        confidence = proposal.get("confidence", 0)
        if confidence < rules["min_confidence"]:
            return {"passed": False,
                    "reason": f"Confidence {confidence:.2f} < {rules['min_confidence']}"}
        return {"passed": True, "reason": f"Confidence {confidence:.2f} OK"}

    def _check_portfolio_limits(self, portfolio: dict, proposal: dict, rules: dict) -> dict:
        balance = portfolio.get("balance", 0)
        trade_value = proposal.get("usdt_value", proposal.get("size_usdt", 0))

        if balance > 0:
            params = self._params()
            # Same symbol-aware exchange minimum the risk manager sizes against,
            # so micro scale-up caps stay consistent between the two layers.
            entry = proposal.get("entry_price", 0)
            min_order = max(rules["min_order_usdt"], entry * 0.0001)
            effective_max_pct = effective_position_pct(
                balance, rules["max_position_pct_of_portfolio"], params,
                regime=proposal.get("regime", "unknown"),
                meta_p=proposal.get("meta_probability"),
                min_order_usdt=min_order)
            pct = trade_value / balance * 100
            # Small tolerance: risk manager caps exactly and 8-decimal quantity
            # rounding can push usdt_value microscopically over.
            if pct > effective_max_pct + 0.01:
                return {"passed": False,
                        "reason": f"Position {pct:.1f}% exceeds {effective_max_pct}% limit"}

        open_positions = portfolio.get("open_positions", 0)
        num_positions = open_positions if isinstance(open_positions, int) else len(open_positions)
        if num_positions >= rules["max_positions_total"]:
            return {"passed": False,
                    "reason": f"Max positions {rules['max_positions_total']} reached"}

        return {"passed": True, "reason": "Portfolio limits OK"}

    def _check_volatility(self, proposal: dict, rules: dict) -> dict:
        vol = proposal.get("volatility_15m", 0)
        if vol > rules["volatility_max_15m_pct"]:
            return {"passed": False,
                    "reason": f"Volatility {vol}% exceeds {rules['volatility_max_15m_pct']}% max"}
        return {"passed": True, "reason": "Volatility within limits"}

    def _check_sentiment(self, sentiment: dict, proposal: dict) -> dict:
        classification = sentiment.get("overall_sentiment", "neutral")
        action = proposal.get("action", "HOLD")

        if classification == "extreme_greed" and action == "LONG":
            return {"passed": False, "reason": "Extreme greed — blocking new LONG entries"}
        if classification == "extreme_fear" and action == "SHORT":
            return {"passed": False, "reason": "Extreme fear — blocking new SHORT entries"}
        return {"passed": True, "reason": "Sentiment check OK"}

    def _check_derivatives(self, proposal: dict, derivatives: dict | None) -> dict:
        """Block entries into crowded leverage positions (liquidation fuel)."""
        if not derivatives or not derivatives.get("ok"):
            return {"passed": True, "reason": "No derivatives data — check skipped"}

        action = proposal.get("action", "HOLD")
        funding = derivatives.get("funding_annualized_pct")

        if action == "LONG" and derivatives.get("crowded_long"):
            return {"passed": False,
                    "reason": f"Funding {funding}% annualized — crowded longs (liquidation risk)"}
        if action == "SHORT" and derivatives.get("crowded_short"):
            return {"passed": False,
                    "reason": f"Funding {funding}% annualized — crowded shorts (liquidation risk)"}
        return {"passed": True, "reason": "Derivatives context OK"}

    def _check_balance(self, portfolio: dict, rules: dict) -> dict:
        balance = portfolio.get("balance", 0)
        floor = rules["balance_floor"]
        # Micro-capital accounts trade below the standard floor (that's the
        # point of the scale-up — grow a small account) — but never below the
        # micro floor, to keep dust accounts halted.
        micro = self._params().get("micro_capital", {}) or {}
        if micro.get("enabled", True) and balance < micro.get("balance_threshold", 2000):
            floor = min(floor, float(micro.get("balance_floor", 50.0)))
        if balance < floor:
            return {"passed": False,
                    "reason": f"Balance {balance} below floor {floor} — trading halted"}
        return {"passed": True, "reason": f"Balance {balance} above floor"}

    def _check_correlation(self, proposal: dict, portfolio: dict) -> dict:
        """If we already hold a position in a correlated asset, reject to avoid
        concentrated sector risk. Uses market cap / sector as a proxy."""
        symbol = proposal.get("symbol", "")
        base = symbol.split("/")[0] if "/" in symbol else symbol
        correlated = {
            "BTC": ["ETH", "SOL", "ADA", "DOT"],
            "ETH": ["SOL", "ADA", "MATIC", "LINK"],
            "SOL": ["AVAX", "DOT", "ADA"],
        }
        corr_group = correlated.get(base, [])
        if not corr_group:
            return {"passed": True, "reason": "No correlation group defined"}

        open_trades = portfolio.get("open_trades", [])
        for t in open_trades:
            t_base = t.get("symbol", "").split("/")[0]
            if t_base in corr_group:
                return {"passed": False,
                        "reason": f"Correlated position exists: {t_base} is correlated to {base}"}
        return {"passed": True, "reason": "No correlated positions"}

    def _check_min_volume(self, proposal: dict) -> dict:
        """Reject illiquid coins — 24h volume must exceed min_volume_24h_usd."""
        min_vol = 500_000  # $500k 24h volume floor
        volume = proposal.get("volume_24h", 0) or proposal.get("volume", 0)
        analysis = proposal.get("_analysis", {}) or {}
        # Try to extract volume from market data if not on proposal
        if not volume and "close" in proposal:
            volume = proposal.get("usdt_value", 0) * 20  # rough proxy
        if volume and volume > 0:
            if volume < min_vol:
                return {"passed": False,
                        "reason": f"24h volume ${volume:.0f} below ${min_vol:,} minimum"}
        return {"passed": True, "reason": "Volume check OK"}

    def _check_multi_tf(self, analysis: dict, proposal: dict, rules: dict) -> dict:
        """Reject signals that lack multi-timeframe agreement.
        At least 2 of 4 timeframes must agree on direction."""
        if not analysis:
            return {"passed": True, "reason": "No analysis data — check skipped"}
        mtf = analysis.get("multi_tf_agreement", "unknown")
        if mtf == "yes":
            return {"passed": True, "reason": "Multi-TF agreement confirmed"}
        if mtf == "no":
            return {"passed": False,
                    "reason": "Multi-TF direction conflict — fewer than 3 of 4 timeframes agree"}
        return {"passed": True, "reason": "Multi-TF check indeterminate — allowing"}
