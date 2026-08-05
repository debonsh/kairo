"""Shadow Engine — test parameters in production without risking capital.
Any parameter the learning layer produces runs in shadow mode against
live data for N cycles before promotion. Same philosophy as Gate:
learned parameters never hot-swap into live capital."""

from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


@dataclass
class ShadowCandidate:
    id: str
    source: str            # "evolver", "calibrator", "meta_labeler"
    param_name: str
    old_value: float | str
    new_value: float | str
    created: datetime = field(default_factory=datetime.now)
    virtual_pnl: float = 0.0
    virtual_trades: int = 0
    cycles_completed: int = 0
    promoted: bool = False
    rejected: bool = False


class ShadowEngine:
    def __init__(self, min_cycles: int = 50, improvement_threshold: float = 0.05):
        self.candidates: list[ShadowCandidate] = []
        self.min_cycles = min_cycles
        self.improvement_threshold = improvement_threshold
        self.active_live_params: dict[str, float] = {}

    def submit(self, source: str, param_name: str, old_value: float,
               new_value: float) -> str:
        import uuid
        cand_id = str(uuid.uuid4())[:8]
        cand = ShadowCandidate(
            id=cand_id, source=source, param_name=param_name,
            old_value=old_value, new_value=new_value,
        )
        self.candidates.append(cand)
        logger.info(f"Shadow: {source}.{param_name} {old_value}→{new_value} [{cand_id}]")
        return cand_id

    def record_cycle(self, candidate_id: str, virtual_pnl: float):
        for cand in self.candidates:
            if cand.id == candidate_id:
                cand.cycles_completed += 1
                cand.virtual_pnl += virtual_pnl
                cand.virtual_trades += 1

                if cand.cycles_completed >= self.min_cycles:
                    self._evaluate(cand)
                break

    def _evaluate(self, candidate: ShadowCandidate):
        if candidate.cycles_completed < self.min_cycles:
            return

        if candidate.virtual_pnl > 0:
            candidate.promoted = True
            self.active_live_params[candidate.param_name] = candidate.new_value
            logger.success(f"Shadow PROMOTED: {candidate.source}.{candidate.param_name} "
                         f"→ {candidate.new_value} (PnL: ${candidate.virtual_pnl:.2f})")
        else:
            candidate.rejected = True
            logger.info(f"Shadow REJECTED: {candidate.source}.{candidate.param_name} "
                       f"→ {candidate.new_value} (PnL: ${candidate.virtual_pnl:.2f})")

    def get_pending(self) -> list[ShadowCandidate]:
        return [c for c in self.candidates if not c.promoted and not c.rejected]

    def get_status(self) -> dict:
        pending = len(self.get_pending())
        promoted = sum(1 for c in self.candidates if c.promoted)
        rejected = sum(1 for c in self.candidates if c.rejected)
        return {
            "total_submitted": len(self.candidates),
            "pending": pending,
            "promoted": promoted,
            "rejected": rejected,
            "active_params": dict(self.active_live_params),
        }
