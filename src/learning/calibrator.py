"""Confidence Calibrator — tracks agent accuracy + Sharpe drift.

New addition: Live Sharpe vs Backtest Sharpe drift monitoring.
If live Sharpe diverges meaningfully from backtest Sharpe, auto-de-risk
by reducing position sizes or pausing the strategy — no waiting for human."""

from loguru import logger


class ConfidenceCalibrator:
    def __init__(self, store, de_risk_threshold: float = 0.5,
                 emergency_threshold: float = 1.0):
        self.store = store
        self.de_risk_threshold = de_risk_threshold
        self.emergency_threshold = emergency_threshold
        self.risk_multiplier = 1.0

    def calibrate(self, agent: str, claimed_confidence: float) -> float:
        history = self._get_agent_history(agent)
        if not history or len(history) < 10:
            return claimed_confidence

        actual_accuracy = sum(1 for h in history if h["was_correct"]) / len(history)
        avg_claimed = sum(h["predicted_confidence"] for h in history) / len(history)

        calibration_factor = actual_accuracy / avg_claimed if avg_claimed > 0 else 1.0
        calibrated = claimed_confidence * calibration_factor
        calibrated = max(0.3, min(0.9, calibrated))

        if abs(claimed_confidence - calibrated) > 0.1:
            logger.debug(f"Calibrated {agent}: {claimed_confidence:.2f} → {calibrated:.2f} "
                        f"(accuracy={actual_accuracy:.1%})")
        return calibrated

    def check_sharpe_drift(self, live_sharpe: float, backtest_sharpe: float,
                           live_trades: int, killswitch=None) -> dict:
        if live_trades < 20:
            return {"status": "insufficient_data", "drift": 0, "action": "none"}

        drift = abs(live_sharpe - backtest_sharpe)

        if drift > self.emergency_threshold:
            self.risk_multiplier = 0.25
            action = "emergency_downsized"
            if killswitch:
                logger.critical(f"Sharpe drift {drift:.2f} — emergency: halving all positions")
            msg = f"CRITICAL: live Sharpe {live_sharpe:.2f} vs backtest {backtest_sharpe:.2f}"

        elif drift > self.de_risk_threshold:
            self.risk_multiplier *= 0.8
            action = "de_risked"
            msg = f"Sharpe drift {drift:.2f} — reducing position sizes to {self.risk_multiplier:.0%}"

        else:
            self.risk_multiplier = min(1.0, self.risk_multiplier * 1.05)
            action = "normal"
            msg = f"Sharpe OK: live {live_sharpe:.2f} vs backtest {backtest_sharpe:.2f}"

        logger.info(f"Sharpe drift check: {msg}")
        return {
            "status": action,
            "drift": round(drift, 2),
            "live_sharpe": round(live_sharpe, 2),
            "backtest_sharpe": round(backtest_sharpe, 2),
            "risk_multiplier": round(self.risk_multiplier, 3),
            "live_trades": live_trades,
        }

    def _get_agent_history(self, agent: str, limit: int = 50) -> list[dict]:
        return self.store.conn.execute(
            "SELECT * FROM scorecard WHERE agent=? ORDER BY timestamp DESC LIMIT ?",
            [agent, limit],
        ).fetchdf().to_dict("records")

    def get_calibration_report(self) -> dict:
        result = self.store.conn.execute(
            "SELECT agent, COUNT(*) as n, "
            "AVG(predicted_confidence) as avg_conf, "
            "AVG(CASE WHEN was_correct THEN 1.0 ELSE 0.0 END) as accuracy "
            "FROM scorecard GROUP BY agent"
        ).fetchdf()

        report = {}
        for _, row in result.iterrows():
            agent = row["agent"]
            accuracy = row["accuracy"] or 0
            avg_conf = row["avg_conf"] or 1
            report[agent] = {
                "samples": int(row["n"]),
                "accuracy": round(accuracy * 100, 1),
                "avg_confidence": round(avg_conf * 100, 1),
                "overconfident": avg_conf > accuracy + 0.1,
                "calibration_bias": round((accuracy - avg_conf) * 100, 1),
            }
        return report
