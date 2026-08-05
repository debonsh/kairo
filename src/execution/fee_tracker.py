"""Fee Tracker — compare live trading costs against backtest model assumptions.
If actual slippage/spread/fees consistently exceed modeled costs,
the strategy edge may be entirely eaten — this catches that.

ponytail: simple running average comparison, alert on 1.5x deviation."""

from collections import deque
from loguru import logger


class FeeTracker:
    def __init__(self, modeled_taker_fee: float = 0.001,
                 modeled_slippage: float = 0.0005, window: int = 50):
        self.modeled_taker = modeled_taker_fee
        self.modeled_slippage = modeled_slippage
        self.window = window

        self.actual_costs: deque = deque(maxlen=window)
        self.actual_slippages: deque = deque(maxlen=window)
        self.trade_count = 0
        self.warnings = 0

    def record(self, trade_id: str, expected_price: float, fill_price: float,
               quantity: float, exchange_fee: float):
        notional = expected_price * quantity
        slip_pct = abs(fill_price - expected_price) / expected_price if expected_price > 0 else 0
        fee_pct = exchange_fee / notional if notional > 0 else 0

        self.actual_costs.append(fee_pct + slip_pct)
        self.actual_slippages.append(slip_pct)
        self.trade_count += 1

    def check_drift(self) -> dict:
        if len(self.actual_costs) < 10:
            return {"status": "insufficient_data", "drift_pct": 0, "action": "none"}

        import statistics
        avg_actual_cost = statistics.mean(self.actual_costs)
        avg_actual_slip = statistics.mean(self.actual_slippages)
        modeled_total = self.modeled_taker + self.modeled_slippage

        drift_ratio = avg_actual_cost / modeled_total if modeled_total > 0 else 1.0

        if drift_ratio > 2.0:
            status, action = "critical", "pause_trading"
            self.warnings += 1
            logger.critical(f"CRITICAL fee drift: actual {avg_actual_cost:.4%} vs modeled {modeled_total:.4%} "
                          f"({drift_ratio:.1f}x). Edge may be consumed by costs.")
        elif drift_ratio > 1.5:
            status, action = "warning", "log_warning"
            self.warnings += 1
            logger.warning(f"Fee drift: actual {avg_actual_cost:.4%} vs modeled {modeled_total:.4%} "
                         f"({drift_ratio:.1f}x)")
        else:
            status, action = "ok", "none"

        return {
            "status": status,
            "action": action,
            "drift_ratio": round(drift_ratio, 2),
            "avg_actual_cost_pct": round(avg_actual_cost * 100, 4),
            "avg_actual_slip_pct": round(avg_actual_slip * 100, 4),
            "modeled_total_pct": round(modeled_total * 100, 4),
            "samples": len(self.actual_costs),
        }

    def get_summary(self) -> dict:
        import statistics
        return {
            "total_trades": self.trade_count,
            "avg_cost_pct": round(statistics.mean(self.actual_costs) * 100, 4) if self.actual_costs else 0,
            "avg_slippage_pct": round(statistics.mean(self.actual_slippages) * 100, 4) if self.actual_slippages else 0,
            "warnings": self.warnings,
            "modeled_cost_pct": round((self.modeled_taker + self.modeled_slippage) * 100, 4),
        }
