"""LLM Fine-Tuning Pipeline — export winning trade decisions for LoRA fine-tuning.

Collects closed trades with detailed agent decision context from DuckDB,
formats them as instruction/input/output JSONL for fine-tuning Qwen 8B
on Kairo's specific trading domain.

Three export modes:
  - strategist: Trade filter decisions (APPROVE/REJECT + reasoning)
  - analyst: Market analysis (direction + confidence + reasoning)
  - risk_manager: Risk assessment (approve/reject + risk checks)

Exports Alpaca/ShareGPT format for unsloth/axolotl training.
"""

import json
import time as time_mod
from pathlib import Path
from datetime import datetime
from loguru import logger


class FinetuneDataExporter:
    def __init__(self, store):
        self.store = store

    def export_strategist(self, output_dir: str | Path, min_trades: int = 50) -> dict:
        """Export Strategist agent data — trade filter decisions.

        Format: {instruction, input: {signal, market_data, sentiment, portfolio},
                 output: {decision, confidence, reasoning}}
        Only exports trades where the strategist's decision matched the outcome.
        """
        return self._export_agent("strategist", output_dir, min_trades)

    def export_analyst(self, output_dir: str | Path, min_trades: int = 50) -> dict:
        """Export Analyst agent data — market analysis with chart context."""
        return self._export_agent("analyst", output_dir, min_trades)

    def export_risk_manager(self, output_dir: str | Path, min_trades: int = 50) -> dict:
        """Export Risk Manager agent data — risk validation decisions."""
        return self._export_agent("risk_manager", output_dir, min_trades)

    def _export_agent(self, agent: str, output_dir: str | Path, min_trades: int) -> dict:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        records = self._fetch_agent_decisions(agent, min_trades)
        if len(records) < min_trades:
            logger.warning(f"Only {len(records)} records for {agent} — need {min_trades}+")
            return {"status": "insufficient_data", "records_found": len(records), "min_required": min_trades}

        # Filter for quality: only keep trades where the agent was correct
        quality_records = []
        for r in records:
            was_correct = r.get("was_correct")
            if was_correct or was_correct is None:  # include if correct or unknown
                quality_records.append(r)

        if len(quality_records) < min_trades // 2:
            logger.warning(f"Quality records too few: {len(quality_records)} < {min_trades // 2}")
            return {"status": "insufficient_quality", "records_found": len(quality_records)}

        # Format as Alpaca instruction tuning data
        jsonl_path = output_dir / f"{agent}_training.jsonl"
        samples_written = 0

        with open(jsonl_path, "w", encoding="utf-8") as f:
            for r in quality_records:
                sample = self._format_sample(agent, r)
                if sample:
                    f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                    samples_written += 1

        logger.success(f"Exported {samples_written} training samples for {agent} → {jsonl_path}")
        return {
            "status": "success",
            "agent": agent,
            "total_records": len(records),
            "quality_records": len(quality_records),
            "samples_exported": samples_written,
            "output_path": str(jsonl_path),
        }

    def _fetch_agent_decisions(self, agent: str, min_trades: int) -> list[dict]:
        """Fetch closed trades with agent decisions and scorecard data."""
        try:
            rows = self.store.conn.execute(
                """SELECT t.id, t.symbol, t.side, t.entry_price, t.exit_price,
                          t.pnl, t.pnl_pct, t.strategy, t.exit_reason,
                          t.entry_time, t.exit_time, t.agent_decision,
                          s.was_correct, s.predicted_confidence, s.agent
                   FROM trades t
                   LEFT JOIN scorecard s ON t.id = s.trade_id AND s.agent = ?
                   WHERE t.status = 'closed' AND t.pnl IS NOT NULL
                   ORDER BY t.exit_time DESC LIMIT 500""",
                [agent],
            ).fetchall()

            records = []
            for row in rows:
                decision = None
                try:
                    decision = json.loads(row[11]) if row[11] else {}
                except (json.JSONDecodeError, TypeError):
                    pass

                records.append({
                    "id": row[0],
                    "symbol": row[1],
                    "side": row[2],
                    "entry_price": row[3],
                    "exit_price": row[4],
                    "pnl": row[5],
                    "pnl_pct": row[6],
                    "strategy": row[7],
                    "exit_reason": row[8],
                    "entry_time": row[9],
                    "exit_time": row[10],
                    "agent_decision": decision,
                    "was_correct": row[12],
                    "predicted_confidence": row[13],
                })

            return records
        except Exception as e:
            logger.warning(f"Fetch agent decisions failed: {e}")
            return []

    def _format_sample(self, agent: str, record: dict) -> dict | None:
        """Format a single trade record into Alpaca instruction format."""
        decision = record.get("agent_decision") or {}
        symbol = record.get("symbol", "?")
        pnl = record.get("pnl", 0)
        side = record.get("side", "?")

        if agent == "strategist":
            return {
                "instruction": "You are a crypto trading strategist. Your job is to filter trade signals — approve good trades and reject bad ones. Consider the market data, sentiment, portfolio state, and past trade outcomes before deciding.",
                "input": json.dumps({
                    "signal": decision.get("signal", {}),
                    "analysis": decision.get("analysis", {}),
                    "sentiment": decision.get("sentiment", {}),
                    "portfolio": decision.get("portfolio", {}),
                }, indent=2),
                "output": json.dumps({
                    "decision": "APPROVE" if pnl > 0 else "REJECT",
                    "confidence": decision.get("confidence", 0.5),
                    "reasoning": decision.get("reason", f"Trade {symbol} {side} with PnL {pnl}"),
                }, indent=2),
            }

        elif agent == "analyst":
            return {
                "instruction": "You are a crypto market analyst. Read the provided market data and give a directional assessment with confidence level and multi-timeframe analysis.",
                "input": json.dumps({
                    "market_data": decision.get("market_data", {}),
                    "symbol": symbol,
                }, indent=2),
                "output": json.dumps({
                    "direction": decision.get("direction", "BULLISH" if pnl > 0 else "BEARISH"),
                    "confidence": decision.get("confidence", 0.5),
                    "reasoning": decision.get("reasoning", []),
                    "multi_tf_agreement": decision.get("multi_tf_agreement", "unknown"),
                }, indent=2),
            }

        elif agent == "risk_manager":
            return {
                "instruction": "You are a risk manager. Validate the proposed trade against absolute risk rules. Flag concerns but default to APPROVE unless a hard rule is clearly violated.",
                "input": json.dumps({
                    "trade_proposal": decision.get("trade", {}),
                    "portfolio": decision.get("portfolio", {}),
                    "risk_rules": decision.get("risk_rules", {}),
                }, indent=2),
                "output": json.dumps({
                    "decision": "APPROVE" if pnl > 0 else "REJECT",
                    "position_size_check": decision.get("position_size_check", "PASS"),
                    "correlation_check": decision.get("correlation_check", "PASS"),
                    "risk_score": decision.get("risk_score", 5),
                }, indent=2),
            }

        return None

    def export_all(self, output_dir: str | Path = "data/finetune", min_trades: int = 50) -> dict:
        """Export all three agents' data in one call."""
        results = {}
        for agent in ["strategist", "analyst", "risk_manager"]:
            results[agent] = self._export_agent(agent, output_dir, min_trades)
        return results

    def get_dataset_stats(self) -> dict:
        """Summary of available training data across all agents."""
        stats = {}
        for agent in ["strategist", "analyst", "risk_manager"]:
            records = self._fetch_agent_decisions(agent, 0)
            quality = sum(1 for r in records if r.get("was_correct") or r.get("was_correct") is None)
            stats[agent] = {
                "total_records": len(records),
                "quality_available": quality,
                "ready_for_training": quality >= 50,
            }
        return stats
