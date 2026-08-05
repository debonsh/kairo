"""Signal Scorecard — tracks agent prediction accuracy over time.
Every agent prediction is scored against the actual outcome.
Used to adjust strategy weights dynamically."""

from datetime import datetime
from loguru import logger


class SignalScorecard:
    def __init__(self, store):
        self.store = store

    def record(self, trade_id: str, agent: str, predicted: str,
               actual: str, confidence: float) -> bool:
        was_correct = predicted.lower() == actual.lower()

        import uuid
        self.store.conn.execute(
            """INSERT INTO scorecard (id, trade_id, predicted_direction, actual_direction,
               predicted_confidence, was_correct, agent)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [str(uuid.uuid4()), trade_id, predicted, actual, confidence, was_correct, agent],
        )
        logger.debug(f"Scorecard recorded: {agent} {'correct' if was_correct else 'wrong'} ({confidence:.0%} conf)")
        return was_correct

    def get_agent_accuracy(self, agent: str, window: int = 50) -> dict:
        result = self.store.conn.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) as correct "
            "FROM scorecard WHERE agent=? ORDER BY timestamp DESC LIMIT ?",
            [agent, window],
        ).fetchone()

        total = result[0] if result else 0
        correct = result[1] if result else 0
        return {
            "agent": agent,
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total * 100, 1) if total > 0 else 0,
            "window": window,
        }

    def get_all_accuracies(self, window: int = 50) -> dict[str, dict]:
        result = self.store.conn.execute(
            "SELECT agent, COUNT(*) as total, SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) as correct "
            "FROM scorecard GROUP BY agent ORDER BY correct DESC"
        ).fetchdf()

        return {
            row["agent"]: {
                "total": int(row["total"]),
                "correct": int(row["correct"]),
                "accuracy": round(row["correct"] / row["total"] * 100, 1) if row["total"] > 0 else 0,
            }
            for _, row in result.iterrows()
        }

    def recent_predictions(self, limit: int = 10) -> list[dict]:
        return self.store.conn.execute(
            "SELECT * FROM scorecard ORDER BY timestamp DESC LIMIT ?", [limit]
        ).fetchdf().to_dict("records")
