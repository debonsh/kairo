"""Decision Memory — injects past trade outcomes into LLM context.
Queries recent closed trades from DuckDB and formats an experience summary
so the strategist can learn from its own outcomes."""

from loguru import logger


class DecisionMemory:
    def __init__(self, store):
        self.store = store

    def get_recent_lessons(self, symbol: str | None = None, limit: int = 10) -> str:
        """Query last N closed trades and format a concise experience summary.

        Returns a string like:
        "Last 5 BTC/USDT trades: +$2.10 (LONG, MA Cross), -$0.80 (LONG, RSI)...
         Pattern: RSI Mean Reversion has been wrong on BTC recently"
        """
        try:
            if symbol:
                rows = self.store.conn.execute(
                    """SELECT symbol, side, entry_price, exit_price, pnl, pnl_pct,
                              strategy, exit_reason, entry_time
                       FROM trades WHERE status='closed' AND symbol=?
                       ORDER BY exit_time DESC LIMIT ?""",
                    [symbol, limit],
                ).fetchall()
            else:
                rows = self.store.conn.execute(
                    """SELECT symbol, side, entry_price, exit_price, pnl, pnl_pct,
                              strategy, exit_reason, entry_time
                       FROM trades WHERE status='closed'
                       ORDER BY exit_time DESC LIMIT ?""",
                    [limit],
                ).fetchall()

            if not rows:
                return "No recent closed trades on record."

            lines = []
            wins = 0
            losses = 0
            strategy_outcomes: dict[str, list[float]] = {}

            for r in rows:
                sym, side, entry, exit_p, pnl, pnl_pct, strat, reason, ts = r
                pnl = pnl or 0
                pnl_pct = pnl_pct or 0
                strat = strat or "unknown"

                prefix = "+" if pnl > 0 else ""
                lines.append(
                    f"{sym} {side}: {prefix}${pnl:.2f} ({pnl_pct:.1f}%) [{strat}] — {reason or '?'}"
                )

                if pnl > 0:
                    wins += 1
                else:
                    losses += 1

                if strat not in strategy_outcomes:
                    strategy_outcomes[strat] = []
                strategy_outcomes[strat].append(pnl)

            summary = f"Recent {len(rows)} closed trades ({wins}W/{losses}L):\n"
            summary += "\n".join(f"  - {line}" for line in lines)

            patterns = self._detect_patterns(strategy_outcomes, symbol)
            if patterns:
                summary += f"\n\nPatterns detected:\n{patterns}"

            return summary

        except Exception as e:
            logger.warning(f"DecisionMemory query failed: {e}")
            return ""

    def _detect_patterns(self, strategy_outcomes: dict[str, list[float]],
                         symbol: str | None = None) -> str:
        """Detect patterns in strategy outcomes."""
        patterns = []
        for strat, pnls in strategy_outcomes.items():
            if len(pnls) < 2:
                continue
            wins = sum(1 for p in pnls if p > 0)
            total = len(pnls)
            win_rate = wins / total

            if win_rate <= 0.3:
                target = f"{symbol} " if symbol else ""
                patterns.append(
                    f"  WARNING: {strat} has been losing on {target}({wins}/{total} wins). "
                    f"Consider reducing weight or rejecting its signals."
                )
            elif win_rate >= 0.7:
                target = f"{symbol} " if symbol else ""
                patterns.append(
                    f"  STRONG: {strat} is performing well on {target}({wins}/{total} wins). "
                    f"Trust its signals more."
                )

        return "\n".join(patterns) if patterns else ""

    def get_memory_context(self, symbol: str | None = None, limit: int = 10) -> str:
        """Return a formatted block ready for injection into LLM prompts."""
        lessons = self.get_recent_lessons(symbol, limit)
        if not lessons:
            return ""
        return f"TRADE MEMORY (past outcomes):\n{lessons}"
