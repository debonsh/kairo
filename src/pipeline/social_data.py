"""Social & Alternative Data Providers.

Free tier providers:
  - CoinGecko: Market data, social stats, trending coins, developer activity
  - LunarCrush: Social mentions, influencer activity, sentiment scores (60 calls/day free)
  - Reddit: r/CryptoCurrency, r/Bitcoin hot posts via public JSON API

All data feeds into the SocialSentimentAgent and DuckDB social_mentions table.
"""

import time
import json
from datetime import datetime
from loguru import logger
import httpx


class CoinGeckoProvider:
    """Free CoinGecko API — no key needed for public endpoints (10-50 calls/min)."""

    BASE = "https://api.coingecko.com/api/v3"

    def __init__(self):
        self._cache: dict[str, dict] = {}
        self._last_fetch: dict[str, float] = {}
        self._cache_ttl = 120  # 2 min for trending, 5 min for coin data

    def get_trending(self) -> list[dict]:
        """Top-15 trending coins on CoinGecko (searches + views)."""
        cache_key = "trending"
        if cache_key in self._last_fetch and time.time() - self._last_fetch[cache_key] < self._cache_ttl:
            return self._cache.get(cache_key, [])

        try:
            resp = httpx.get(f"{self.BASE}/search/trending", timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                coins = data.get("coins", [])
                result = []
                for item in coins[:15]:
                    c = item.get("item", {})
                    result.append({
                        "id": c.get("id", ""),
                        "symbol": c.get("symbol", "").upper(),
                        "name": c.get("name", ""),
                        "market_cap_rank": c.get("market_cap_rank"),
                        "score": c.get("score", 0),
                    })
                self._cache[cache_key] = result
                self._last_fetch[cache_key] = time.time()
                logger.debug(f"CoinGecko: {len(result)} trending coins")
                return result
        except Exception as e:
            logger.debug(f"CoinGecko trending failed: {e}")
        return []

    def get_coin_data(self, coin_id: str) -> dict | None:
        """Full coin data: price, market cap, community sentiment, developer stats."""
        cache_key = f"coin_{coin_id}"
        if cache_key in self._last_fetch and time.time() - self._last_fetch[cache_key] < 300:
            return self._cache.get(cache_key)

        try:
            resp = httpx.get(
                f"{self.BASE}/coins/{coin_id}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "community_data": "true",
                    "developer_data": "true",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                market = data.get("market_data", {})
                community = data.get("community_data", {})
                developer = data.get("developer_data", {})
                result = {
                    "id": data.get("id"),
                    "symbol": data.get("symbol", "").upper(),
                    "name": data.get("name"),
                    "sentiment_votes_up": data.get("sentiment_votes_up_percentage", 50),
                    "sentiment_votes_down": 100 - data.get("sentiment_votes_up_percentage", 50),
                    "market_cap": market.get("market_cap", {}).get("usd"),
                    "total_volume": market.get("total_volume", {}).get("usd"),
                    "price_change_24h": market.get("price_change_percentage_24h"),
                    "twitter_followers": community.get("twitter_followers"),
                    "reddit_subscribers": community.get("reddit_subscribers"),
                    "reddit_avg_posts_48h": community.get("reddit_average_posts_48h"),
                    "telegram_channel_user_count": community.get("telegram_channel_user_count"),
                    "forks": developer.get("forks"),
                    "stars": developer.get("stars"),
                    "commit_count_4w": developer.get("commit_count_4_weeks"),
                }
                self._cache[cache_key] = result
                self._last_fetch[cache_key] = time.time()
                return result
        except Exception as e:
            logger.debug(f"CoinGecko {coin_id} failed: {e}")
        return None

    def get_market_chart(self, coin_id: str, days: int = 7) -> dict | None:
        """OHLCV + market cap + volume chart data."""
        try:
            resp = httpx.get(
                f"{self.BASE}/coins/{coin_id}/market_chart",
                params={"vs_currency": "usd", "days": days},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "prices": data.get("prices", []),
                    "market_caps": data.get("market_caps", []),
                    "total_volumes": data.get("total_volumes", []),
                }
        except Exception:
            pass
        return None


class LunarCrushProvider:
    """LunarCrush API — social metrics for crypto (60 calls/day free)."""

    BASE = "https://lunarcrush.com/api4/public"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or ""
        self._cache: dict[str, dict] = {}
        self._last_fetch: dict[str, float] = {}
        self._cache_ttl = 600  # 10 min — rate limited

    def get_coin_social(self, symbol: str) -> dict | None:
        """Per-coin social metrics from LunarCrush."""
        cache_key = f"lc_{symbol}"
        if cache_key in self._last_fetch and time.time() - self._last_fetch[cache_key] < self._cache_ttl:
            return self._cache.get(cache_key)

        try:
            resp = httpx.get(
                f"{self.BASE}/coins/{symbol.lower()}/v1",
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                self._cache[cache_key] = data
                self._last_fetch[cache_key] = time.time()
                return data
        except Exception as e:
            logger.debug(f"LunarCrush {symbol}: {e}")

        return None

    def get_social_metrics(self, symbol: str) -> dict:
        """Extract key social metrics with fallback to empty default."""
        data = self.get_coin_social(symbol) or {}
        return {
            "symbol": symbol.upper(),
            "social_volume": data.get("social_volume", 0),
            "social_score": data.get("social_score", 0),
            "social_contributors": data.get("social_contributors", 0),
            "sentiment": data.get("sentiment", 0.5),
            "galaxy_score": data.get("galaxy_score", 0),
            "alt_rank": data.get("alt_rank", 9999),
            "spam_volume": data.get("spam_volume", 0),
            "influencer_activity": data.get("influencer_activity", 0),
        }


class RedditProvider:
    """Reddit public JSON API via old.reddit.com — free, no key needed."""

    SUBREDDITS = ["CryptoCurrency", "Bitcoin", "ethereum", "CryptoMarkets"]

    def __init__(self):
        self._cache: dict[str, list] = {}
        self._last_fetch = 0
        self._cache_ttl = 300

    def fetch_hot_posts(self, limit: int = 25) -> list[dict]:
        if time.time() - self._last_fetch < self._cache_ttl:
            return self._cache.get("hot", [])

        all_posts = []
        for sub in self.SUBREDDITS:
            try:
                resp = httpx.get(
                    f"https://old.reddit.com/r/{sub}/hot.json",
                    params={"limit": limit},
                    headers={
                        "User-Agent": "KairoBot/1.0 (by /u/kairo_bot)",
                        "Accept": "application/json",
                    },
                    timeout=15,
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                children = data.get("data", {}).get("children", [])
                for child in children:
                    post = child.get("data", {})
                    all_posts.append({
                        "subreddit": sub,
                        "title": post.get("title", ""),
                        "selftext": post.get("selftext", "")[:200],
                        "score": post.get("score", 0),
                        "num_comments": post.get("num_comments", 0),
                        "upvote_ratio": post.get("upvote_ratio", 0.5),
                        "created_utc": post.get("created_utc", 0),
                        "url": post.get("url", ""),
                        "author": str(post.get("author", "unknown")),
                    })
            except Exception as e:
                logger.debug(f"Reddit r/{sub}: {e}")

        all_posts.sort(key=lambda p: p.get("score", 0), reverse=True)
        self._cache["hot"] = all_posts[:50]
        self._last_fetch = time.time()
        logger.info(f"Reddit: {len(all_posts)} posts from {len(self.SUBREDDITS)} subs")
        return all_posts[:50]


class SocialDataAggregator:
    """Fetches from all social providers + CoinGecko and merges results per symbol."""

    COINGECKO_ID_MAP = {
        "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
        "BNB": "binancecoin", "XRP": "ripple", "DOGE": "dogecoin",
        "ADA": "cardano", "AVAX": "avalanche-2", "DOT": "polkadot",
        "SUI": "sui", "ARB": "arbitrum", "OP": "optimism",
        "FET": "fetch-ai", "RENDER": "render-token", "TIA": "celestia",
        "SEI": "sei-network", "PEPE": "pepe",
    }

    def __init__(self):
        self.coingecko = CoinGeckoProvider()
        self.lunarcrush = LunarCrushProvider()
        self.reddit = RedditProvider()

    def fetch_all(self, symbols: list[str]) -> dict[str, dict]:
        """Fetch all social data for a list of symbols. Returns {BTC: {...}, ETH: {...}}."""
        results = {}

        # CoinGecko trending
        trending = self.coingecko.get_trending()
        trending_symbols = {t["symbol"] for t in trending}

        # Reddit
        reddit_posts = self.reddit.fetch_hot_posts()

        for sym in symbols[:8]:
            coin_id = self.COINGECKO_ID_MAP.get(sym)
            cg_data = self.coingecko.get_coin_data(coin_id) if coin_id else None
            lc_data = self.lunarcrush.get_social_metrics(sym)

            # Count reddit mentions for this symbol
            sym_lower = sym.lower()
            reddit_mentions = sum(
                1 for p in reddit_posts
                if sym_lower in p["title"].lower() or sym_lower in p.get("selftext", "").lower()
            )

            # CoinGecko community sentiment
            cg_sentiment = cg_data.get("sentiment_votes_up", 50) if cg_data else 50

            # Aggregate score
            social_score = (
                (lc_data.get("galaxy_score", 0) or 0) * 0.3
                + (lc_data.get("social_score", 0) or 0) * 0.25
                + cg_sentiment * 0.15
                + min(reddit_mentions * 5, 50) * 0.2
                + (10 if sym in trending_symbols else 0) * 0.1
            )

            results[sym] = {
                "symbol": sym,
                "trending": sym in trending_symbols,
                "coingecko_sentiment": cg_sentiment / 100,
                "lunarcrush_sentiment": lc_data.get("sentiment", 0.5),
                "social_volume": lc_data.get("social_volume", 0) or 0,
                "influencer_activity": lc_data.get("influencer_activity", 0) or 0,
                "reddit_mentions": reddit_mentions,
                "twitter_followers": cg_data.get("twitter_followers", 0) if cg_data else 0,
                "reddit_subscribers": cg_data.get("reddit_subscribers", 0) if cg_data else 0,
                "galaxy_score": lc_data.get("galaxy_score", 0) or 0,
                "alt_rank": lc_data.get("alt_rank", 9999) or 9999,
                "social_score": round(social_score, 1),
                "timestamp": int(time.time() * 1000),
            }

        return results
