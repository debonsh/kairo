"""Strategist Agent — VETO-ONLY gate for LLM context check.
DOES NOT originate trade signals. Signals come from SignalEngine (deterministic,
backtest-validated strategies + meta-label filter). The LLM's role is to
provide context: "does this trade make sense given current news/regime?"

The LLM can VETO a trade (output: REJECT) but CANNOT force one.
If the SignalEngine says HOLD, there is no trade to discuss."""

from pathlib import Path
from loguru import logger
from .llm_client import LLMClient


class StrategistAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm
        prompt_path = Path("config/prompts/strategist.txt")
        self.prompt_template = prompt_path.read_text() if prompt_path.exists() else ""

    def filter(self, signal: dict, analysis: dict, sentiment: dict,
               portfolio: dict, symbol: str, memory: str = "") -> dict:
        """Filter a SignalEngine proposal — approve or veto. Do NOT originate."""
        if signal.get("action") == "HOLD":
            return {"filter_action": "HOLD", "confidence": signal.get("confidence", 0),
                    "reason": "SignalEngine produced HOLD — nothing to filter"}

        prompt = self._build_filter_prompt(signal, analysis, sentiment, portfolio, symbol, memory)

        try:
            response = self.llm.ask(prompt, temperature=0.2, max_tokens=400)
        except Exception as e:
            logger.warning(f"Strategist LLM unavailable: {e} — defaulting to APPROVE")
            return self._default_approve(signal)

        return self._parse_filter_response(response, signal)

    def _build_filter_prompt(self, signal: dict, analysis: dict,
                              sentiment: dict, portfolio: dict, symbol: str,
                              memory: str = "") -> str:
        import json
        prompt = self.prompt_template if self.prompt_template else ""
        replacements = {
            "{{signal}}": json.dumps(signal, indent=2, default=str),
            "{{analysis}}": json.dumps(analysis, indent=2, default=str),
            "{{sentiment}}": json.dumps(sentiment, indent=2, default=str),
            "{{portfolio}}": json.dumps(portfolio, indent=2, default=str),
            "{{memory}}": memory or "No past trade data available yet.",
        }
        for placeholder, value in replacements.items():
            prompt = prompt.replace(placeholder, value)
        return prompt

    def _parse_filter_response(self, response, signal: dict) -> dict:
        text = (response.text or "").upper()

        if not text.strip():
            # Empty response (e.g. thinking model ate its token budget) —
            # default to approve, matching the "IF UNSURE: APPROVE" rule.
            return self._default_approve(signal, reason="Empty LLM response — defaulting to approve (gate enforces limits)")

        approved = "APPROVE" in text[:100]
        confidence = signal.get("confidence", 0.5)

        if "REJECT" in text[:100]:
            approved = False
            extracted = self._extract_confidence(response.text)
            confidence = extracted if extracted else confidence * 0.5

        return {
            "filter_action": "APPROVE" if approved else "REJECT",
            "confidence": min(confidence, 0.95),
            "reason": response.text[:200],
            "signal": signal,
            "source": "strategist_filter",
        }

    def _extract_confidence(self, text: str) -> float | None:
        try:
            import re
            match = re.search(r"Confidence.*?([0-9.]+)", text)
            if match:
                return float(match.group(1))
        except (ValueError, AttributeError):
            pass
        return None

    def _default_approve(self, signal: dict, reason: str | None = None) -> dict:
        return {
            "filter_action": "APPROVE",
            "confidence": signal.get("confidence", 0.5) * 0.8,
            "reason": reason or "LLM unavailable — defaulting to approve (SignalEngine validated)",
            "signal": signal,
            "source": "strategist_filter_fallback",
        }
