"""Position management — stop-loss, take-profit, partial-TP, trailing stop,
and the max-hold time-stop (48h rule).

Positions close on SL / TP / trailing / partial-TP / rotation / kill switch
/ time-stop. The time-stop (``position.max_hold_time_hours`` in
risk_rules.yaml, default 48h) is now ENFORCED: a position that never hits
SL or TP in a choppy regime must not sit open forever, occupying one of the
5 position slots and tying up capital.

Partial take-profit: when price hits the first TP target, we close 50-70%
of the position and lock the rest with a breakeven stop."""

import time as time_mod
from loguru import logger


class PositionManager:
    def __init__(self, store, trail_activation_pct: float = 0.01,
                 trail_distance_pct: float = 0.005,
                 partial_tp_pct: float = 0.5,        # close 50%% at first TP
                 partial_tp_ratio: float = 0.5,       # TP at 50%% of original target
                 partial_tp_to_breakeven: bool = True,
                 state_manager=None,                  # reads live risk_rules params
                 max_hold_time_hours: float = 48.0):  # enforced fallback if no state mgr
        self.store = store
        self.trail_activation_pct = trail_activation_pct
        self.trail_distance_pct = trail_distance_pct
        self.partial_tp_pct = partial_tp_pct
        self.partial_tp_ratio = partial_tp_ratio
        self.partial_tp_to_breakeven = partial_tp_to_breakeven
        self.state_manager = state_manager
        self.max_hold_time_hours = max_hold_time_hours

    def _resolved_max_hold_hours(self) -> float:
        """Max hold from the live active profile (risk_rules.yaml), falling
        back to the constructor default when no state manager is wired."""
        if self.state_manager is not None:
            try:
                params = self.state_manager.get_active_params()
                position = params.get("position", {})
                if position.get("max_hold_time_hours"):
                    return float(position["max_hold_time_hours"])
            except Exception:
                pass
        return self.max_hold_time_hours

    def get_open_positions(self) -> list[dict]:
        return self.store.get_open_positions()

    def check_exits(self, current_prices: dict[str, float], paper_trader) -> list[dict]:
        closed = []
        for pos in self.get_open_positions():
            symbol = pos["symbol"]
            if symbol not in current_prices:
                continue

            price = float(current_prices[symbol])
            sl = pos.get("stop_loss")
            tp = pos.get("take_profit")
            entry = float(pos["entry_price"])
            side = pos["side"]
            pos_id = pos.get("id", "")

            if sl is not None:
                sl = float(sl)
            if tp is not None:
                tp = float(tp)

            self._update_trailing_stop(pos_id, entry, price, side, sl, tp)

            # Partial take-profit: hit first TP target, close 50%% and move to breakeven
            if tp is not None and tp > 0 and not pos.get("_partial_executed"):
                partial_tp = self._check_partial_tp(entry, price, side, tp, pos, paper_trader, pos_id)
                if partial_tp:
                    closed.append(partial_tp)
                    continue  # remaining position still lives with breakeven

            updated_pos = self.store.conn.execute(
                "SELECT stop_loss, quantity, status FROM trades WHERE id=?", [pos_id]
            ).fetchone()
            if updated_pos:
                if updated_pos[2] == 'closed':
                    continue  # already closed by partial-TP action
                if updated_pos[0]:
                    sl = float(updated_pos[0])
                current_qty = float(updated_pos[1]) if updated_pos[1] else 0
            else:
                current_qty = pos.get("quantity", 0)

            exit_reason = None

            if side in ("long", "buy"):
                if sl is not None and sl > 0 and price <= sl:
                    exit_reason = "trailing_stop" if sl > entry else "stop_loss"
                elif tp is not None and tp > 0 and price >= tp:
                    exit_reason = "take_profit"
            else:
                if sl is not None and sl > 0 and price >= sl:
                    exit_reason = "trailing_stop" if sl < entry else "stop_loss"
                elif tp is not None and tp > 0 and price <= tp:
                    exit_reason = "take_profit"

            # Time-stop — the 48h rule, now enforced. A position that never
            # hits SL/TP (choppy regime) must not sit open forever: it occupies
            # one of the max_positions_total slots and ties up capital. SL/TP
            # checks take precedence — this only fires when neither did.
            if exit_reason is None:
                max_hold_hours = self._resolved_max_hold_hours()
                entry_time = pos.get("entry_time")
                if max_hold_hours and entry_time:
                    age_hours = (int(time_mod.time() * 1000) - int(entry_time)) / 3_600_000
                    if age_hours >= max_hold_hours:
                        exit_reason = "time_stop"
                        logger.info(f"Exit {symbol} @ {price} | reason=time_stop "
                                   f"age={age_hours:.1f}h >= max {max_hold_hours:.0f}h")

            if exit_reason:
                logger.info(f"Exit {symbol} @ {price} | reason={exit_reason} "
                           f"entry={entry} sl={sl} tp={tp} qty={current_qty:.4f}")
                paper_trader.close_position(pos, price, exit_reason)
                closed.append(pos)

        return closed

    def _check_partial_tp(self, entry: float, price: float, side: str,
                          tp: float, pos: dict, paper_trader, pos_id: str) -> dict | None:
        """If price touches a partial-TP level (50%% of full TP target),
        close half the position and move the stop to breakeven."""
        if side in ("long", "buy"):
            partial_target = entry + (tp - entry) * self.partial_tp_ratio
            if price >= partial_target:
                qty = pos.get("quantity", 0)
                close_qty = qty * self.partial_tp_pct
                if close_qty < 0.00001:
                    return None
                remainder_qty = qty - close_qty
                logger.info(f"Partial TP @ {price:.2f} for {pos['symbol']}: "
                           f"closing {self.partial_tp_pct*100:.0f}%% (qty {close_qty:.6f}), "
                           f"keeping {remainder_qty:.6f}")

                # Update DB: reduce quantity and move SL to entry (breakeven)
                self.store.conn.execute(
                    "UPDATE trades SET quantity=?, stop_loss=? WHERE id=?",
                    [remainder_qty, entry, pos_id]
                )
                pos["_partial_executed"] = True
                pos["quantity"] = remainder_qty
                pos["stop_loss"] = entry

                # Log the partial close as a separate trade in paper trader
                partial_trade = dict(pos)
                partial_trade["quantity"] = close_qty
                partial_trade["exit_reason"] = "partial_tp"
                paper_trader.partial_close(partial_trade, price)
                return partial_trade
        else:  # short
            partial_target = entry - (entry - tp) * self.partial_tp_ratio
            if price <= partial_target:
                qty = pos.get("quantity", 0)
                close_qty = qty * self.partial_tp_pct
                if close_qty < 0.00001:
                    return None
                remainder_qty = qty - close_qty
                logger.info(f"Partial TP @ {price:.2f} for {pos['symbol']}: "
                           f"closing {self.partial_tp_pct*100:.0f}%%")
                self.store.conn.execute(
                    "UPDATE trades SET quantity=?, stop_loss=? WHERE id=?",
                    [remainder_qty, entry, pos_id]
                )
                pos["_partial_executed"] = True
                pos["quantity"] = remainder_qty
                pos["stop_loss"] = entry

                partial_trade = dict(pos)
                partial_trade["quantity"] = close_qty
                partial_trade["exit_reason"] = "partial_tp"
                paper_trader.partial_close(partial_trade, price)
                return partial_trade
        return None

    def _update_trailing_stop(self, pos_id: str, entry: float, price: float,
                               side: str, current_sl: float | None, tp: float | None):
        if side in ("long", "buy"):
            pnl_pct = (price - entry) / entry if entry > 0 else 0
            if pnl_pct >= self.trail_activation_pct:
                new_sl = price * (1 - self.trail_distance_pct)
                if current_sl is None or new_sl > current_sl:
                    self.store.conn.execute(
                        "UPDATE trades SET stop_loss=? WHERE id=?", [new_sl, pos_id]
                    )
        else:  # short
            pnl_pct = (entry - price) / entry if entry > 0 else 0
            if pnl_pct >= self.trail_activation_pct:
                new_sl = price * (1 + self.trail_distance_pct)
                if current_sl is None or new_sl < current_sl:
                    self.store.conn.execute(
                        "UPDATE trades SET stop_loss=? WHERE id=?", [new_sl, pos_id]
                    )

    def get_pnl_summary(self) -> dict:
        trades = self.store.conn.execute(
            "SELECT * FROM trades WHERE status='closed' ORDER BY exit_time DESC LIMIT 50"
        ).fetchdf()

        if len(trades) == 0:
            return {"total_pnl": 0, "win_rate": 0, "total_trades": 0}

        winning = trades[trades["pnl"] > 0]
        return {
            "total_pnl": round(float(trades["pnl"].sum()), 2),
            "total_trades": len(trades),
            "winning_trades": len(winning),
            "win_rate": round(len(winning) / len(trades) * 100, 1),
            "avg_win": round(float(winning["pnl"].mean()), 2) if len(winning) > 0 else 0,
            "avg_loss": round(float(trades[trades["pnl"] <= 0]["pnl"].mean()), 2) if len(trades[trades["pnl"] <= 0]) > 0 else 0,
        }
