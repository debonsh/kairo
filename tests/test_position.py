"""Quick test for position management.

Uses an isolated temp DuckDB file — the live bot holds data/market.db open
and accumulates real positions, so testing against the production DB is
neither safe nor deterministic.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline.store import MarketStore
from src.execution.paper import PaperTrader
from src.execution.position import PositionManager

tmp_db = os.path.join(tempfile.gettempdir(), "kairo_test_position.db")
if os.path.exists(tmp_db):
    os.remove(tmp_db)

store = MarketStore(db_path=tmp_db)
paper = PaperTrader(store, initial_balance=5000.0)

trade = paper.open_position("BTC/USDT", "buy", 63000.0, 0.0015,
                            stop_loss=62055.0, take_profit=64890.0)
assert trade, "Trade not created"
print(f"Open: id={trade['id']} SL={trade['stop_loss']} TP={trade['take_profit']}")

positions = store.get_open_positions()
assert len(positions) == 1, f"Expected 1 open, got {len(positions)}"
db_pos = positions[0]
print(f"DB: SL={db_pos.get('stop_loss')} TP={db_pos.get('take_profit')}")

pm = PositionManager(store)

result = pm.check_exits({"BTC/USDT": 63000.0}, paper)
assert len(result) == 0, f"Should NOT close at entry: got {len(result)}"

result = pm.check_exits({"BTC/USDT": 62000.0}, paper)
assert len(result) == 1, "Should close below SL"

assert len(paper.open_trades) == 0, f"open_trades not cleaned: {len(paper.open_trades)}"
assert paper.balance < 5000, "Balance should reflect fees"

# --- 48h time-stop (roadmap P0.1) ---
import time as time_mod

trade2 = paper.open_position("ETH/USDT", "buy", 3000.0, 0.5,
                             stop_loss=2900.0, take_profit=3200.0)
assert trade2, "Trade2 not created"
# Backdate the entry_time past the max hold so the time-stop fires.
old_time = int(time_mod.time() * 1000) - (49 * 3600 * 1000)
store.conn.execute("UPDATE trades SET entry_time=? WHERE id=?", [old_time, trade2["id"]])

pm2 = PositionManager(store, max_hold_time_hours=48.0)
result = pm2.check_exits({"ETH/USDT": 3005.0}, paper)  # between SL and TP
assert len(result) == 1, "Time-stop should close a 49h-old position"
assert result[0]["symbol"] == "ETH/USDT"

trade3 = paper.open_position("SOL/USDT", "buy", 150.0, 2.0,
                             stop_loss=145.0, take_profit=165.0)
# Fresh entry — must NOT time-stop.
result = pm2.check_exits({"SOL/USDT": 150.5}, paper)
assert len(result) == 0, "Fresh position must not time-stop"

print("ALL POSITION TESTS PASSED (incl. 48h time-stop)")
store.close()

try:
    os.remove(tmp_db)
except OSError:
    pass
