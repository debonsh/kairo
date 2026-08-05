"""Prompt Evolver — improves agent prompts based on trading outcomes.
Analyzes patterns in winning and losing trades, identifies what worked,
and suggests prompt refinements for better future decisions.

ponytail: simple pattern matching on win/loss streaks, add semantic drift
detection if prompts start diverging too far from original intent."""

from pathlib import Path
from loguru import logger
from src.agents.llm_client import LLMClient


class PromptEvolver:
    def __init__(self, llm: LLMClient, store):
        self.llm = llm
        self.store = store
        self.evolution_count = 0
        self.prompt_backups = {}

    def evolve(self, agent_name: str, min_trades: int = 20) -> bool:
        scorecard = self._get_recent_performance(agent_name, min_trades)
        if not scorecard or scorecard["total"] < min_trades:
            logger.debug(f"Not enough trades for {agent_name} evolution ({scorecard.get('total', 0)}/{min_trades})")
            return False

        prompt_path = Path(f"config/prompts/{agent_name}.txt")
        if not prompt_path.exists():
            return False

        evolution_prompt = self._build_evolution_prompt(agent_name, scorecard, prompt_path.read_text())

        try:
            response = self.llm.ask(evolution_prompt, temperature=0.5, max_tokens=800, provider="ollama")
        except Exception as e:
            logger.warning(f"Prompt evolution failed for {agent_name}: {e}")
            return False

        new_prompt = self._extract_prompt(response.text)
        if new_prompt and len(new_prompt) > 50:
            self._backup(agent_name, prompt_path)
            prompt_path.write_text(new_prompt)
            self.evolution_count += 1
            logger.info(f"Prompt evolved for {agent_name} (evolution #{self.evolution_count})")
            return True

        return False

    def _get_recent_performance(self, agent: str, limit: int) -> dict:
        result = self.store.conn.execute(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) as correct "
            "FROM scorecard WHERE agent=? ORDER BY timestamp DESC LIMIT ?",
            [agent, limit],
        ).fetchone()

        if not result:
            return {"total": 0, "correct": 0, "accuracy": 0}

        total, correct = result[0], result[1]
        return {
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total * 100, 1) if total > 0 else 0,
        }

    def _build_evolution_prompt(self, agent_name: str, scorecard: dict, current_prompt: str) -> str:
        return f"""You are improving an AI trading system's prompt template.

The {agent_name} agent has a {scorecard['accuracy']}% accuracy over {scorecard['total']} trades.

Current prompt:
```
{current_prompt[:2000]}
```

Analyze what might be causing the accuracy rate. Suggest improvements.
Output ONLY the revised prompt text, nothing else.
Keep the same OUTPUT FORMAT section.
Remove any ambiguity or vagueness.
Add specific criteria for when to be confident and when to doubt.
"""

    def _extract_prompt(self, text: str) -> str | None:
        text = text.strip()
        if "```" in text:
            parts = text.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:
                    clean = part.strip()
                    if clean.startswith("txt") or clean.startswith("prompt"):
                        clean = clean[clean.find("\n"):] if "\n" in clean else clean
                    return clean.strip()
        return text if len(text) > 50 else None

    def _backup(self, agent_name: str, prompt_path: Path):
        import shutil
        backup_path = Path("config/prompts") / f"{agent_name}.v{self.evolution_count}.txt"
        shutil.copy(prompt_path, backup_path)
        self.prompt_backups.setdefault(agent_name, []).append(str(backup_path))

    def rollback(self, agent_name: str) -> bool:
        backups = self.prompt_backups.get(agent_name, [])
        if not backups:
            return False
        last_backup = Path(backups[-1])
        current = Path(f"config/prompts/{agent_name}.txt")
        from shutil import copy
        copy(last_backup, current)
        backups.pop()
        logger.info(f"Rolled back {agent_name} to {last_backup}")
        return True
