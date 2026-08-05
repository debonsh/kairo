"""Futures Gate — statistical gate before perpetual futures orders are allowed.
Enforces the requirements from config/settings.yaml futures_gate section:
  50+ spot trades, Sharpe >= 1.2, win rate >= 0.40, 5+ profitable days.

Also checks trading mode (vanilla vs aggressive) to set leverage cap.
Vanilla = spot only (1x). Aggressive = futures allowed (up to 2x)."""

import time as time_mod
from dataclasses import dataclass, field
from loguru import logger
import yaml
from pathlib import Path


@dataclass
class FuturesGateResult:
    unlocked: bool
    allowed_leverage: float
    total_spot_trades: int = 0
    rolling_sharpe: float = 0.0
    win_rate: float = 0.0
    profitable_days: int = 0
    checks: dict[str, bool] = field(default_factory=dict)
    reason: str = ""


class FuturesGate:
    def __init__(self, store, mode: str = "vanilla"):
        self.store = store
        self.mode = mode
        self._config = self._load_config()

    def _load_config(self) -> dict:
        path = Path("config/settings.yaml")
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f).get("futures_gate", {})
        return {}

    def evaluate(self) -> FuturesGateResult:
        """Run all gate checks. Returns unlocked=True only if ALL pass."""
        checks = {
            "min_trades": self._check_min_trades(),
            "sharpe": self._check_sharpe(),
            "win_rate": self._check_win_rate(),
            "profitable_days": self._check_profitable_days(),
        }
        all_passed = all(checks.values())

        if self.mode == "aggressive":
            if all_passed:
                allowed_leverage = 2.0
                reason = "Gate passed + aggressive mode: 2x leverage allowed"
            else:
                failed = [k for k, v in checks.items() if not v]
                allowed_leverage = 1.0
                reason = f"Aggressive mode but gate not passed. Failed: {failed}. Spot only (1x)"
        else:
            allowed_leverage = 1.0
            reason = f"Vanilla mode: spot only (1x leverage). " + (
                "Gate passed but mode restricts leverage." if all_passed else
                f"Gate failed: {[k for k, v in checks.items() if not v]}"
            )

        stats = self._compute_stats()

        return FuturesGateResult(
            unlocked=all_passed,
            allowed_leverage=allowed_leverage,
            total_spot_trades=stats["total_spot_trades"],
            rolling_sharpe=round(stats["rolling_sharpe"], 3),
            win_rate=round(stats["win_rate"], 4),
            profitable_days=stats["profitable_days"],
            checks=checks,
            reason=reason,
        )

    def _check_min_trades(self) -> bool:
        threshold = self._config.get("min_trades", 50)
        count = self._count_spot_trades()
        return count >= threshold

    def _check_sharpe(self) -> bool:
        min_sharpe = 1.2  # hard floor
        stats = self._compute_stats()
        return stats["rolling_sharpe"] >= min_sharpe

    def _check_win_rate(self) -> bool:
        min_wr = self._config.get("min_win_rate", 0.40)
        stats = self._compute_stats()
        return stats["win_rate"] >= min_wr

    def _check_profitable_days(self) -> bool:
        min_days = self._config.get("min_consecutive_profitable_days", 5)
        consecutive = self._count_consecutive_profitable_days()
        return consecutive >= min_days

    def _count_spot_trades(self) -> int:
        try:
            result = self.store.conn.execute(
                "SELECT COUNT(*) FROM trades WHERE status='closed'"
            ).fetchone()
            return int(result[0]) if result else 0
        except Exception:
            return 0

    def _compute_stats(self) -> dict:
        """Compute rolling stats from closed trades."""
        try:
            rows = self.store.conn.execute(
                "SELECT pnl, exit_time FROM trades WHERE status='closed' AND pnl IS NOT NULL ORDER BY exit_time DESC LIMIT 200"
            ).fetchall()
            if not rows:
                return {"total_spot_trades": 0, "rolling_sharpe": 0.0, "win_rate": 0.0, "profitable_days": 0}

            pnls = [float(r[0]) for r in rows if r[0] is not None]
            total = len(pnls)
            wins = sum(1 for p in pnls if p > 0)

            win_rate = wins / total if total > 0 else 0.0

            returns = [p / 5000.0 for p in pnls]
            avg = sum(returns) / len(returns) if returns else 0.0
            variance = sum((r - avg) ** 2 for r in returns) / len(returns) if returns else 1.0
            std = variance ** 0.5
            sharpe = (avg / std * (252 ** 0.5)) if std > 0 else 0.0

            profitable_days = self._count_consecutive_profitable_days()

            return {
                "total_spot_trades": total,
                "rolling_sharpe": sharpe,
                "win_rate": win_rate,
                "profitable_days": profitable_days,
            }
        except Exception as e:
            logger.debug(f"FuturesGate stats failed: {e}")
            return {"total_spot_trades": 0, "rolling_sharpe": 0.0, "win_rate": 0.0, "profitable_days": 0}

    def _count_consecutive_profitable_days(self) -> int:
        """Count consecutive profitable days from most recent to past."""
        try:
            rows = self.store.conn.execute(
                """SELECT DATE_TRUNC('day', to_timestamp(exit_time / 1000)) as day,
                          SUM(pnl) as daily_pnl
                   FROM trades WHERE status='closed' AND pnl IS NOT NULL
                   GROUP BY day ORDER BY day DESC LIMIT 30"""
            ).fetchall()

            if not rows:
                return 0

            consecutive = 0
            for row in rows:
                daily_pnl = float(row[1]) if row[1] else 0
                if daily_pnl > 0:
                    consecutive += 1
                else:
                    break

            return consecutive
        except Exception:
            try:
                rows = self.store.conn.execute(
                    """SELECT exit_time, pnl FROM trades WHERE status='closed' AND pnl IS NOT NULL ORDER BY exit_time DESC"""
                ).fetchall()
                if not rows:
                    return 0

                from datetime import datetime
                daily_pnls: dict[str, float] = {}
                for exit_time, pnl in rows:
                    if exit_time and pnl:
                        day = datetime.fromtimestamp(int(exit_time) / 1000).strftime("%Y-%m-%d")
                        daily_pnls[day] = daily_pnls.get(day, 0) + float(pnl)

                sorted_days = sorted(daily_pnls.keys(), reverse=True)
                consecutive = 0
                for day in sorted_days:
                    if daily_pnls[day] > 0:
                        consecutive += 1
                    else:
                        break
                return consecutive
            except Exception:
                return 0

    def set_mode(self, mode: str):
        mode = mode.lower()
        if mode not in ("vanilla", "aggressive"):
            raise ValueError(f"Unknown mode: {mode}. Use 'vanilla' or 'aggressive'.")
        old = self.mode
        self.mode = mode
        logger.info(f"FuturesGate mode: {old} → {mode}")

    def get_mode(self) -> str:
        return self.mode
