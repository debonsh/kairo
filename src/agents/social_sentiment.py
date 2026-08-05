"""Social Sentiment Agent — aggregates social data, detects extreme sentiment.

Key signals:
  - Crowd euphoria (extreme bullish social score) = contrarian BEARISH signal
  - Crowd panic (extreme bearish social score) = contrarian BULLISH signal
  - Rising social volume = increased attention (can precede volatility)
  - Influencer activity spike = potential manipulation / pump risk
  - Trending on CoinGecko = retail FOMO risk

The agent produces a CROWD_BIAS that feeds into the Strategist LLM prompt
as a modifier — never a primary trade signal.
"""

import time
from loguru import logger
from .llm_client import LLMClient
from ..pipeline.social_data import SocialDataAggregator


class SocialSentimentAgent:
    def __init__(self, llm: LLMClient | None = None, store=None):
        self.llm = llm
        self.store = store
        self.aggregator = SocialDataAggregator()
        self._batch_cache: dict[str, dict] = {}
        self._last_batch_fetch: float = 0.0
        self._batch_cache_ttl: float = 600.0  # 10 min between full API fetches

    def prefetch(self, symbols: list[str], force: bool = False):
        """Fetch social data for ALL tracked coins in ONE batch API call.

        Call this once at the top of the trading cycle — then get_context_for_llm()
        reads from in-memory cache with zero network I/O.
        """
        now = time.time()
        if not force and self._batch_cache and (now - self._last_batch_fetch) < self._batch_cache_ttl:
            return  # still fresh

        try:
            raw = self.aggregator.fetch_all(symbols)
            signals = {}
            for sym, data in raw.items():
                signals[sym] = self._analyze(sym, data)

            self._batch_cache = signals
            self._last_batch_fetch = now

            if self.store:
                self._persist(signals)

            logger.info(f"Social prefetch: {len(signals)} symbols cached")
        except Exception as e:
            logger.warning(f"Social prefetch failed: {e}")

    def gather(self, symbol: str) -> dict:
        """Get social sentiment for a single symbol from batch cache."""
        return self._batch_cache.get(symbol, self._empty_signal(symbol))

    def gather_batch(self, symbols: list[str]) -> dict[str, dict]:
        """Read from in-memory batch cache — no API calls."""
        return {s: self._batch_cache.get(s, self._empty_signal(s)) for s in symbols}

    def _analyze(self, symbol: str, data: dict) -> dict:
        """Convert raw social data into trading-relevant signals."""
        social_score = data.get("social_score", 0)

        # Sentiment intensity
        cg_sent = data.get("coingecko_sentiment", 0.5)
        lc_sent = data.get("lunarcrush_sentiment", 0.5)
        composite_sentiment = (cg_sent * 0.3 + lc_sent * 0.7) if lc_sent else cg_sent

        # Crowding detection
        is_extreme_bullish = composite_sentiment > 0.85
        is_extreme_bearish = composite_sentiment < 0.15
        is_trending = data.get("trending", False)

        # Contrarian signal
        if is_extreme_bullish or is_trending:
            crowd_bias = "bearish"
            reason = f"Extreme crowd bullish ({composite_sentiment:.1%}). Contrarian: potential top."
        elif is_extreme_bearish:
            crowd_bias = "bullish"
            reason = f"Extreme crowd bearish ({composite_sentiment:.1%}). Contrarian: potential bottom."
        else:
            crowd_bias = "neutral"
            reason = f"Social sentiment {composite_sentiment:.1%} — no extreme reading."

        # Risk flags
        risk_flags = []
        influ_activity = data.get("influencer_activity", 0) or 0
        if influ_activity > 80:
            risk_flags.append("HIGH_INFLUENCER_ACTIVITY")
        if data.get("social_volume", 0) > 10000:
            risk_flags.append("ELEVATED_SOCIAL_VOLUME")
        if is_trending:
            risk_flags.append("TRENDING_COINGECKO")
        if (data.get("alt_rank", 9999) or 9999) < 100:
            risk_flags.append("HIGH_ALT_RANK")

        return {
            "symbol": symbol,
            "social_score": social_score,
            "composite_sentiment": round(composite_sentiment, 3),
            "crowd_bias": crowd_bias,
            "reason": reason,
            "risk_flags": risk_flags,
            "is_trending": is_trending,
            "social_volume": data.get("social_volume", 0) or 0,
            "influencer_activity": influ_activity,
            "reddit_mentions": data.get("reddit_mentions", 0),
            "galaxy_score": data.get("galaxy_score", 0) or 0,
            "timestamp": int(time.time() * 1000),
        }

    def _persist(self, signals: dict[str, dict]):
        """Save social data to DuckDB for later analysis."""
        try:
            rows = []
            for sym, signal in signals.items():
                rows.append({
                    "symbol": sym,
                    "timestamp": int(time.time() * 1000),
                    "source": "social_aggregator",
                    "mentions": signal.get("social_volume", 0) or 0,
                    "sentiment_score": signal.get("composite_sentiment", 0.5),
                    "sentiment_label": signal.get("crowd_bias", "neutral"),
                    "headline_count": signal.get("reddit_mentions", 0),
                    "trending_score": signal.get("galaxy_score", 0) or 0,
                })
            self.store.conn.executemany(
                """INSERT OR REPLACE INTO social_mentions
                   VALUES ($symbol, $timestamp, $source, $mentions, $sentiment_score,
                           $sentiment_label, $headline_count, $trending_score)""",
                rows,
            )
        except Exception as e:
            logger.debug(f"Social persist skip: {e}")

    def get_context_for_llm(self, symbol: str) -> str:
        """Format social signals as a concise text block for the Strategist LLM prompt."""
        data = self.gather(symbol)
        if not data or data == self._empty_signal(symbol):
            return ""

        lines = [
            f"SOCIAL SENTIMENT ({symbol}):",
            f"  Composite Sentiment: {data['composite_sentiment']:.1%}",
            f"  Crowd Bias: {data['crowd_bias'].upper()}",
            f"  Social Volume: {data.get('social_volume', 0):,.0f} mentions",
            f"  Reddit Mentions: {data.get('reddit_mentions', 0)} recent posts",
            f"  Trending: {'YES' if data.get('is_trending') else 'no'}",
            f"  Galaxy Score: {data.get('galaxy_score', 0)}",
            f"  Reason: {data.get('reason', 'N/A')}",
        ]
        if data.get("risk_flags"):
            lines.append(f"  Risk Flags: {', '.join(data['risk_flags'])}")
        return "\n".join(lines)

    @staticmethod
    def _empty_signal(symbol: str) -> dict:
        return {
            "symbol": symbol,
            "social_score": 0,
            "composite_sentiment": 0.5,
            "crowd_bias": "neutral",
            "reason": "No social data available",
            "risk_flags": [],
            "is_trending": False,
            "social_volume": 0,
            "influencer_activity": 0,
            "reddit_mentions": 0,
            "galaxy_score": 0,
            "timestamp": int(time.time() * 1000),
        }
