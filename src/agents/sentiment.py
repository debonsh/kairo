"""Sentiment Agent — real-time news + Fear & Greed + backtest-validated signals.

Pulls live RSS headlines each cycle (not stale model pretraining).
Fear & Greed must pass backtest validation before it gets operational weight."""

import httpx
import feedparser
import asyncio
import re
from datetime import datetime
from loguru import logger
from .llm_client import LLMClient
from src.backtest.feature_test import FeatureTester


class SentimentAgent:
    FEAR_GREED_URL = "https://api.alternative.me/fng/"
    RSS_SOURCES = {
        "cryptopanic": "https://cryptopanic.com/posts/index.rss",
        "cointelegraph": "https://cointelegraph.com/rss",
        "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    }

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm
        self.feature_tester = FeatureTester()
        self._fng_validated = False
        self._fng_ic: float | None = None
        self._fng_p_value: float | None = None
        self._news_cache: dict[str, list] = {}
        self._last_news_fetch = datetime.min

    def validate_fear_greed(self, fng_history: list[float],
                            forward_returns: list[float]) -> dict:
        """Validate Fear & Greed predictive value before using it in trading."""
        import numpy as np
        result = self.feature_tester.test_predictive_value(
            np.array(fng_history), np.array(forward_returns), horizon=5
        )
        self._fng_validated = result.predictive
        self._fng_ic = result.information_coefficient
        self._fng_p_value = result.p_value
        logger.info(f"Fear & Greed validation: predictive={result.predictive} "
                    f"IC={result.information_coefficient:.4f} p={result.p_value:.4f}")
        return {
            "predictive": result.predictive,
            "ic": result.information_coefficient,
            "p_value": result.p_value,
            "notes": result.notes,
        }

    async def gather(self, symbol: str) -> dict:
        results = {}

        try:
            fg = await self._fetch_fear_greed()
            results["fear_greed"] = fg
        except Exception as e:
            logger.warning(f"Fear & Greed fetch failed: {e}")
            results["fear_greed"] = {"value": 50, "classification": "Neutral"}

        try:
            headlines = await self._fetch_news(symbol)
            results["headlines"] = headlines
            results["news_sentiment"] = self._score_headlines(headlines)
        except Exception as e:
            logger.warning(f"News fetch failed: {e}")
            results["headlines"] = []
            results["news_sentiment"] = {"score": 0, "sentiment": "neutral", "count": 0}

        results["symbol"] = symbol
        results["timestamp"] = int(datetime.now().timestamp() * 1000)
        results["overall_sentiment"] = self._categorize(results)
        results["fng_validated"] = self._fng_validated

        return results

    def gather_sync(self, symbol: str) -> dict:
        return asyncio.run(self.gather(symbol))

    async def _fetch_fear_greed(self) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.FEAR_GREED_URL}?limit=1")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data"):
                    item = data["data"][0]
                    return {
                        "value": int(item.get("value", 50)),
                        "classification": item.get("value_classification", "Neutral"),
                        "timestamp": item.get("timestamp", ""),
                    }
        return {"value": 50, "classification": "Neutral"}

    async def _fetch_news(self, symbol: str, max_items: int = 15) -> list[dict]:
        now = datetime.now()
        if (now - self._last_news_fetch).total_seconds() < 120 and symbol in self._news_cache:
            return self._news_cache[symbol]

        headlines = []
        coin_name = symbol.split("/")[0].lower()

        for source_name, url in self.RSS_SOURCES.items():
            try:
                feed = await asyncio.to_thread(feedparser.parse, url)
                for entry in feed.entries[:max_items // len(self.RSS_SOURCES) or 5]:
                    title = entry.get("title", "")
                    if self._is_relevant(title, coin_name):
                        headlines.append({
                            "source": source_name,
                            "title": title,
                            "published": entry.get("published", ""),
                            "link": entry.get("link", ""),
                        })
            except Exception as e:
                logger.debug(f"RSS {source_name} failed: {e}")

        self._news_cache[symbol] = headlines
        self._last_news_fetch = now
        return headlines

    def _is_relevant(self, title: str, coin_name: str) -> bool:
        title_lower = title.lower()
        keywords = [coin_name, "bitcoin" if coin_name == "btc" else "",
                     "ethereum" if coin_name == "eth" else "",
                     "crypto", "blockchain", "defi", "exchange", "sec",
                     "regulation", "hack", "upgrade", "halving", "etf"]
        keywords = [k for k in keywords if k]
        return any(k in title_lower and len(k) > 2 for k in keywords)

    def _score_headlines(self, headlines: list[dict]) -> dict:
        if not headlines:
            return {"score": 0, "sentiment": "neutral", "count": 0}

        positive = ["surge", "rally", "bull", "breakout", "upgrade", "adoption",
                     "partnership", "launch", "new high", "record", "billion"]
        negative = ["crash", "dump", "hack", "sec", "ban", "regulation",
                     "lawsuit", "bear", "decline", "liquidat", "delay"]

        score = 0
        for h in headlines:
            title = h["title"].lower()
            score += sum(1 for w in positive if w in title)
            score -= sum(1 for w in negative if w in title)

        if score > 2:
            sentiment = "positive"
        elif score < -2:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {"score": score, "sentiment": sentiment, "count": len(headlines)}

    def _categorize(self, results: dict) -> str:
        fg = results.get("fear_greed", {})
        value = fg.get("value", 50)
        news = results.get("news_sentiment", {}).get("sentiment", "neutral")

        if not self._fng_validated:
            weight_fg, weight_news = 0.0, 0.5
        else:
            weight_fg, weight_news = 0.5, 0.5

        fg_score = (value - 50) / 50
        news_score = 0.5 if news == "positive" else -0.5 if news == "negative" else 0
        composite = fg_score * weight_fg + news_score * weight_news

        if composite > 0.3:
            return "bullish" if self._fng_validated else "cautiously_bullish"
        elif composite < -0.3:
            return "bearish" if self._fng_validated else "cautiously_bearish"
        return "neutral"

    def get_trading_bias(self, sentiment_data: dict) -> dict:
        fg = sentiment_data.get("fear_greed", {})
        value = fg.get("value", 50)
        classification = sentiment_data.get("overall_sentiment", "neutral")

        bias_map = {
            "bearish": ("sell_biased", "Strong bearish signals — bias toward exits"),
            "cautiously_bearish": ("cautious_sell", "Bearish lean — tighten stops"),
            "neutral": ("neutral", "No strong sentiment signal"),
            "cautiously_bullish": ("cautious_buy", "Mildly bullish — normal trading"),
            "bullish": ("buy_biased", "Strong bullish signals — bias toward entries"),
        }
        bias, signal = bias_map.get(classification, ("neutral", "No signal"))

        return {
            "bias": bias,
            "signal": signal,
            "value": value,
            "classification": classification,
            "fng_validated": self._fng_validated,
            "headline_count": len(sentiment_data.get("headlines", [])),
        }
