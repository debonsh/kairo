"""Portfolio Rotator — auto-swap weak coin positions for stronger coins.
Evaluates multi-timeframe confluence scores for all tracked coins and
rotates out of weakening positions into strengthening ones when the
expected gain exceeds swap fees × 1.5."""

from loguru import logger


class PortfolioRotator:
    def __init__(self, fee_pct: float = 0.001):
        self.fee_pct = fee_pct
        self._coin_scores: dict[str, dict] = {}

    def update_scores(self, coin: str, direction: str, confidence: float,
                      regime: str = "unknown"):
        """Record a coin's latest signal engine score."""
        self._coin_scores[coin] = {
            "direction": direction,
            "confidence": confidence,
            "regime": regime,
        }

    def evaluate(self, portfolio: dict, current_prices: dict[str, float]) -> list[dict]:
        """Rank coins and generate swap instructions for open positions.

        Returns a list of swap dicts:
        [{action: "swap", sell: "BTC/USDT", buy: "ETH/USDT",
          sell_reason: "...", buy_reason: "...", score_delta: 0.42, ...}]
        """
        open_trades = portfolio.get("open_trades", [])
        if len(open_trades) < 1:
            return []

        scored_coins = self._rank_coins()
        if not scored_coins:
            return []

        swaps = []
        for trade in open_trades:
            symbol = trade.get("symbol", "")
            side = trade.get("side", "long")
            entry_price = float(trade.get("entry_price", 0) or 0)

            if symbol not in current_prices:
                continue
            current_price = current_prices[symbol]
            if entry_price <= 0:
                continue

            pnl_pct = (current_price - entry_price) / entry_price
            if side in ("short", "sell"):
                pnl_pct = -pnl_pct

            current_score = self._coin_scores.get(symbol, {})
            current_conf = current_score.get("confidence", 0)

            best_coin, best_data = scored_coins[0]

            if best_coin == symbol:
                continue

            best_conf = best_data.get("confidence", 0)
            score_delta = best_conf - current_conf

            if score_delta < 0.3:
                continue

            best_direction = best_data.get("direction", "HOLD")
            if best_direction == "HOLD":
                continue

            best_price = current_prices.get(best_coin, 0)
            if best_price <= 0:
                continue

            if not self._fee_check(pnl_pct, score_delta):
                continue

            swaps.append({
                "action": "swap",
                "sell_symbol": symbol,
                "buy_symbol": best_coin,
                "sell_side": side,
                "buy_side": best_direction.lower(),
                "sell_current_conf": round(current_conf, 3),
                "buy_conf": round(best_conf, 3),
                "score_delta": round(score_delta, 3),
                "sell_regime": current_score.get("regime", "?"),
                "buy_regime": best_data.get("regime", "?"),
                "sell_value": trade.get("usdt_value", 0),
            })

        return swaps

    def _rank_coins(self) -> list[tuple[str, dict]]:
        """Rank all tracked coins by direction-weighted confidence (highest first)."""
        scored = []
        for coin, data in self._coin_scores.items():
            direction = data.get("direction", "HOLD")
            confidence = data.get("confidence", 0)
            if direction == "HOLD":
                confidence *= 0.2
            scored.append((coin, {**data, "rank_score": confidence}))
        scored.sort(key=lambda x: x[1]["rank_score"], reverse=True)
        return scored

    def _fee_check(self, pnl_pct: float, score_delta: float) -> bool:
        """Only swap if expected alpha > fees × 1.5."""
        round_trip_fees = self.fee_pct * 2
        fee_multiplier = 1.5
        min_gain = round_trip_fees * fee_multiplier

        expected_alpha = score_delta * 0.005
        return expected_alpha > min_gain

    def clear(self):
        """Reset scores between full cycles."""
        self._coin_scores.clear()
