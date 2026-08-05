"""Daily Journal — AI-written trading summary.
Generated at configurable time (default 8 PM IST).
Covers: trades taken, P&L, what worked, what didn't, tomorrow's focus."""

from datetime import datetime, timedelta
from loguru import logger
from .llm_client import LLMClient


class DailyJournal:
    def __init__(self, llm: LLMClient, store):
        self.llm = llm
        self.store = store

    def generate(self) -> str:
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        trades = self._get_trades_since(yesterday)
        scorecard = self._get_scorecard_since(yesterday)

        if not trades:
            return f"# Daily Journal — {today}\n\nNo trades today. Market was quiet."

        summary = self._build_summary(trades, scorecard)
        journal_text = self._llm_journal(summary)

        logger.info(f"Daily journal generated for {today}")
        return journal_text

    def _get_trades_since(self, since_date) -> list[dict]:
        result = self.store.conn.execute(
            "SELECT * FROM trades WHERE entry_time >= ? ORDER BY entry_time DESC",
            [str(since_date)],
        ).fetchdf()
        return result.to_dict("records") if len(result) > 0 else []

    def _get_scorecard_since(self, since_date) -> dict:
        try:
            result = self.store.conn.execute(
                "SELECT agent, COUNT(*) as total, SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) as correct "
                "FROM scorecard WHERE timestamp >= ? GROUP BY agent",
                [str(since_date)],
            ).fetchdf()
            return result.to_dict("records") if len(result) > 0 else []
        except Exception:
            return []

    def _build_summary(self, trades: list[dict], scorecard: list[dict]) -> dict:
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        winning = [t for t in trades if t.get("pnl", 0) > 0]
        losing = [t for t in trades if t.get("pnl", 0) <= 0]

        return {
            "total_trades": len(trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "total_pnl": round(total_pnl, 2),
            "win_rate": round(len(winning) / len(trades) * 100, 1) if trades else 0,
            "best_trade": max(trades, key=lambda t: t.get("pnl", 0)).get("pnl", 0) if trades else 0,
            "worst_trade": min(trades, key=lambda t: t.get("pnl", 0)).get("pnl", 0) if trades else 0,
            "trades": trades[-10:],
            "scorecard": scorecard,
        }

    def _llm_journal(self, summary: dict) -> str:
        prompt = f"""Write a concise daily trading journal entry. Be honest about mistakes.

SUMMARY:
{summary}

FORMAT:
# Daily Journal — {{date}}
## Performance
- Trades: X | Wins: Y | Losses: Z | Win Rate: A%
- P&L: $X
- Best: $X | Worst: $X

## What Worked
- (2-3 bullets)

## What Didn't
- (2-3 bullets, be honest)

## Tomorrow's Focus
- (1-2 actionable items)"""

        try:
            response = self.llm.ask(prompt, temperature=0.4, max_tokens=600)
            return response.text
        except Exception as e:
            logger.warning(f"Journal LLM failed: {e}")
            return self._fallback_journal(summary)

    def _fallback_journal(self, summary: dict) -> str:
        today = datetime.now().date()
        return f"""# Daily Journal — {today}

## Performance
- Trades: {summary['total_trades']} | Wins: {summary['winning_trades']} | Losses: {summary['losing_trades']} | Win Rate: {summary['win_rate']}%
- P&L: ${summary['total_pnl']}
- Best trade: ${summary['best_trade']} | Worst trade: ${summary['worst_trade']}

## Notes
- Journal generated without LLM assistance (offline).
- Review today's trades manually.

## Tomorrow's Focus
- Continue with risk limits. Review strategy weights.
"""
