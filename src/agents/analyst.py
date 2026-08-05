"""Market Analyst Agent — reads structured data, produces market assessment."""

from pathlib import Path
from .llm_client import LLMClient, LLMResponse


class AnalystAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm
        prompt_path = Path("config/prompts/analyst.txt")
        self.prompt_template = prompt_path.read_text() if prompt_path.exists() else ""

    def analyze(self, market_data: dict, symbol: str) -> dict:
        market_text = self._format_market_data(market_data, symbol)
        prompt = self.prompt_template.replace("{{market_data}}", market_text)

        try:
            response = self.llm.ask_with_fallback(prompt, temperature=0.3, max_tokens=512)
        except Exception as e:
            return self._fallback_analysis(market_data, symbol, str(e))

        if response.parsed:
            return self._parse_response(response.parsed, response)
        return self._parse_text(response.text, response)

    def _format_market_data(self, data: dict, symbol: str) -> str:
        lines = [f"Symbol: {symbol}", ""]

        for tf in ["15m", "1h", "4h", "1d"]:
            if tf in data:
                d = data[tf]
                lines.append(f"--- {tf} Timeframe ---")
                lines.append(f"Price: {d.get('close', 'N/A')}")
                lines.append(f"RSI(14): {d.get('rsi', 'N/A')}")
                lines.append(f"MACD: {d.get('macd', 'N/A')} | Signal: {d.get('macd_signal', 'N/A')}")
                lines.append(f"BB Upper/Lower: {d.get('bb_upper', 'N/A')} / {d.get('bb_lower', 'N/A')}")
                lines.append(f"Volume: {d.get('volume', 'N/A')}")
                lines.append(f"SMA20: {d.get('sma20', 'N/A')} | SMA50: {d.get('sma50', 'N/A')}")
                lines.append(f"ATR: {d.get('atr', 'N/A')}")

        if "sentiment" in data:
            lines.append(f"\n--- Sentiment ---")
            lines.append(f"Fear & Greed: {data['sentiment'].get('value', 'N/A')} ({data['sentiment'].get('classification', 'N/A')})")

        lines.append(f"\nMulti-Timeframe Analysis:")
        mtf = self._compute_mtf_confluence(data)
        lines.append(f"Confluence: {mtf['direction']} (agreement: {mtf['agreement']}/4)")
        lines.append(f"Trend strength: {mtf['strength']}")

        return "\n".join(lines)

    def _compute_mtf_confluence(self, data: dict) -> dict:
        signals = []
        for tf in ["15m", "1h", "4h", "1d"]:
            if tf in data:
                d = data[tf]
                sma20 = d.get("sma20", 0)
                sma50 = d.get("sma50", 0)
                close = d.get("close", 0)
                if close and sma20 and sma50:
                    if close > sma20 > sma50:
                        signals.append("bullish")
                    elif close < sma20 < sma50:
                        signals.append("bearish")
                    else:
                        signals.append("neutral")

        bullish = signals.count("bullish")
        bearish = signals.count("bearish")
        if bullish > bearish:
            direction, agreement = "bullish", bullish
        elif bearish > bullish:
            direction, agreement = "bearish", bearish
        else:
            direction, agreement = "neutral", len(signals)

        strength_map = {4: "strong", 3: "moderate", 2: "weak", 1: "very_weak", 0: "none"}
        return {"direction": direction, "agreement": agreement, "strength": strength_map.get(agreement, "none")}

    def _fallback_analysis(self, data: dict, symbol: str, error: str) -> dict:
        mtf = self._compute_mtf_confluence(data)
        return {
            "direction": mtf["direction"].upper(),
            "confidence": min(mtf["agreement"] / 4, 0.7),
            "reasoning": [f"Deterministic fallback — LLM unavailable: {error}",
                         f"Multi-TF confluence: {mtf['direction']} ({mtf['agreement']}/4)"],
            "multi_tf_agreement": "yes" if mtf["agreement"] >= 3 else "no",
            "risk_assessment": "medium",
            "provider": "fallback",
            "model": "deterministic",
            "latency_ms": 0,
        }

    def _parse_response(self, parsed: dict, response: LLMResponse) -> dict:
        return {
            "direction": parsed.get("Direction", "NEUTRAL").upper(),
            "confidence": float(parsed.get("Confidence", 0.5)),
            "reasoning": parsed.get("Reasoning", []),
            "multi_tf_agreement": parsed.get("Multi-TF Agreement", "no"),
            "risk_assessment": parsed.get("Risk Assessment", "medium"),
            "provider": response.provider,
            "model": response.model,
            "latency_ms": response.latency_ms,
        }

    def _parse_text(self, text: str, response: LLMResponse) -> dict:
        text_lower = text.lower()
        if "bullish" in text_lower:
            direction, confidence = "BULLISH", 0.6
        elif "bearish" in text_lower:
            direction, confidence = "BEARISH", 0.6
        else:
            direction, confidence = "NEUTRAL", 0.5

        return {
            "direction": direction,
            "confidence": confidence,
            "reasoning": [text[:200]],
            "multi_tf_agreement": "unknown",
            "risk_assessment": "medium",
            "provider": response.provider,
            "model": response.model,
            "latency_ms": response.latency_ms,
        }
