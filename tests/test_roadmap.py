"""Tests for roadmap v1.1 components (P0.2 info bars, P0.4 meta trust,
P1.1 market maker, P1.2 tri-arb, P2.1 joint sizer, P2.2 fill validation).

Each test uses an isolated temp DuckDB file — the live bot holds
data/market.db open, so testing against the production DB is neither safe
nor deterministic.
"""
import os
import sys
import tempfile
import time as time_mod
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from src.pipeline.store import MarketStore
from src.pipeline.info_bars import (
    candles_to_info_bars, CUSUMBars,
)


def _tmp_db(name: str) -> str:
    path = os.path.join(tempfile.gettempdir(), f"kairo_test_{name}.db")
    if os.path.exists(path):
        os.remove(path)
    return path


def _fake_exchange(tickers: dict):
    """Minimal exchange stub with fetch_ticker."""
    class FakeExchange:
        exchange_id = "bybit"

        def fetch_ticker(self, symbol):
            return tickers.get(symbol, {"last": 0, "bid": 0, "ask": 0})

    return FakeExchange()


# ---------------------------------------------------------------------- #
def test_info_bars_conversion():
    """Volume bars aggregate time candles by volume threshold (P0.2)."""
    candles = [[i * 60_000, 100, 101, 99, 100 + i * 0.1, 200] for i in range(60)]
    bars = candles_to_info_bars(candles, bar_type="volume", threshold=500.0)
    # 60 candles * 200 volume = 12000 total -> ~24 bars at 500 threshold
    assert len(bars) > 5, f"Expected many volume bars, got {len(bars)}"
    bar = bars[0]
    assert len(bar) == 6, "Info bars should be [ts, o, h, l, c, v]"
    assert bar[5] >= 500, "Bar volume should meet threshold"


def test_cusum_bars():
    bars = CUSUMBars(threshold=0.5, warmup=10)
    out = []
    for i in range(100):
        price = 100 + (i % 7) * 3  # choppy then trending pattern
        b = bars.add_tick(price, 10, i * 60_000)
        if b:
            out.append(b)
    assert len(out) > 0, "CUSUM should flush bars"


def test_market_maker_inventory_and_skew():
    """Market maker quotes both sides, fills on trade-through, enforces skew."""
    db = _tmp_db("mm")
    store = MarketStore(db_path=db)
    try:
        from src.execution.market_maker import MarketMaker

        mm = MarketMaker(store, symbols=["BTC/USDT"], spread_pct=0.002,
                         quote_size_usdt=100.0, max_inventory_usdt=1000.0,
                         max_inventory_skew_pct=0.5, fee_pct=0.001)

        # Cycle 1 at 100: quotes only (no standing quote yet -> no fills).
        fills = mm.cycle({"BTC/USDT": 100.0})
        assert len(fills) == 0, "First cycle only establishes the quote"

        # Cycle 2 at 99.5: crosses the standing bid (99.9) -> buy fill.
        fills = mm.cycle({"BTC/USDT": 99.5})
        assert len(fills) == 1 and fills[0]["side"] == "buy", f"Expected buy fill, got {fills}"
        assert mm.inventory["BTC/USDT"] > 0
        assert mm.fills == 1

        # Inventory now long; skew < 0.5 -> still quoting both sides.
        q = mm.last_quote["BTC/USDT"]
        assert q["quoting"]["bid"] is True and q["quoting"]["ask"] is True

        # Pump descending prices so each cycle trades through the standing
        # bid, pushing inventory/skew past the cap -> bid quoting stops.
        # The per-cycle step (2%) must exceed the half-spread (0.1%) or the
        # price never crosses the standing bid. Once the skew gate trips,
        # fills self-limit; enough cycles guarantees the gate is observed.
        price = 99.5
        for _ in range(40):
            price *= 0.98
            mm.cycle({"BTC/USDT": price})
        q = mm.last_quote["BTC/USDT"]
        assert q["quoting"]["bid"] is False, "Skewed-long maker must stop adding buys"
        assert mm.status()["total_realized_pnl"] is not None

        # DB log written
        count = store.conn.execute("SELECT COUNT(*) FROM market_making").fetchone()[0]
        assert count == mm.fills, f"DB has {count} fills, expected {mm.fills}"
    finally:
        store.close()
        os.remove(db)


def test_triangular_arb_detection():
    """Tri-arb finds a profitable loop when the cross rate is mispriced."""
    db = _tmp_db("tri")
    store = MarketStore(db_path=db)
    try:
        from src.execution.triangular_arb import TriangularArbitrage

        # Construct a mispricing: BTC/USDT=100, ETH/USDT=3, but ETH/BTC
        # cross implies 0.028 (vs fair 0.03) -> USDT->BTC->ETH->USDT profits.
        tickers = {
            "BTC/USDT": {"last": 100.0, "bid": 100.0, "ask": 100.01},
            "ETH/USDT": {"last": 3.0, "bid": 2.999, "ask": 3.001},
            "ETH/BTC": {"last": 0.028, "bid": 0.0279, "ask": 0.0281},
        }
        ex = _fake_exchange(tickers)
        ta = TriangularArbitrage(ex, store=store, fee_pct=0.0005, paper_trader=None)

        opps = ta.scan(["BTC", "ETH"])
        profitable = [o for o in opps if o["profitable"]]
        assert len(profitable) >= 1, f"Expected a profitable loop, got {opps}"

        # DB logged
        count = store.conn.execute("SELECT COUNT(*) FROM tri_arb_opportunities").fetchone()[0]
        assert count == len(opps), f"Expected {len(opps)} logged, got {count}"
    finally:
        store.close()
        os.remove(db)


def test_joint_sizer_falls_back_without_correlation():
    """Joint sizer needs >=2 symbols + correlation data; else falls back."""
    db = _tmp_db("joint")
    store = MarketStore(db_path=db)
    try:
        from src.agents.joint_sizer import JointPositionSizer

        js = JointPositionSizer(store)
        if not js.available():
            return  # cvxpy not installed — nothing to assert

        # No candles -> no correlation -> fallback (adjusted == original).
        result = js.size_with_open(
            {"symbol": "BTC/USDT", "entry_price": 100, "meta_probability": 0.6},
            [{"symbol": "ETH/USDT", "usdt_value": 200}],
            {"balance": 5000}, {}, size_usdt=100.0,
        )
        assert result["joint"] is False
        assert result["adjusted_usdt"] == 100.0

        # With synthetic correlated history, solver should run.
        from src.agents.joint_sizer import JointPositionSizer as J2
        for sym in ("BTC/USDT", "ETH/USDT"):
            t0 = int(time_mod.time() * 1000) - 2000 * 60_000
            candles = [[t0 + i * 60_000, 100, 101, 99, 100 + i * 0.01, 1000]
                       for i in range(300)]
            store.insert_candles("bybit", sym, "15m", candles)

        solve = js.solve(["BTC/USDT", "ETH/USDT"], [0.05, 0.1], [500.0, 400.0],
                         5000.0, max_single_pct=0.25)
        assert solve["solved"] is True, f"Joint solve failed: {solve}"
    finally:
        store.close()
        os.remove(db)


def test_fill_validation_simulator():
    """Fill simulator reports a fill-rate curve from stored candles (P2.2)."""
    db = _tmp_db("fill")
    store = MarketStore(db_path=db)
    try:
        from src.backtest.fill_validation import FillSimulator

        t0 = int(time_mod.time() * 1000) - 2000 * 60_000
        # A trending series: closes drift up, so buy-limit fills are rare,
        # sell-limit fills common — both reported.
        candles = [[t0 + i * 60_000, 100 + i * 0.1, 102 + i * 0.1, 99 + i * 0.1,
                    100 + i * 0.1, 1000] for i in range(200)]
        store.insert_candles("bybit", "BTC/USDT", "15m", candles)

        result = FillSimulator.simulate(store, "BTC/USDT",
                                        offsets_pct=[0.1, 0.5], latency_ms=200)
        assert len(result["fill_rates"]) == 2
        assert 0 <= result["fill_rates"][0] <= 100
    finally:
        store.close()
        os.remove(db)


def test_meta_labeler_sample_trust():
    """Meta-labeler carries training_samples + trusted flag (P0.4)."""
    from src.backtest.meta_labeling import MetaLabelClassifier

    mlc = MetaLabelClassifier(min_trusted_samples=100)
    assert mlc.predict(np.zeros(12))["trusted"] is False

    rng = np.random.default_rng(42)
    X = rng.normal(size=(200, 12)).astype(np.float32)
    y = (X[:, 0] + X[:, 1] > 0).astype(np.int64)
    mlc.train(X, y)
    assert mlc.is_trained
    assert mlc.training_samples == 200
    result = mlc.predict(X[0])
    assert result["sample_size"] == 200
    assert result["trusted"] is True
    assert result["caveat"] is None


def test_confidence_sweep_script():
    """Sweep tool runs end-to-end on a temp DB with synthetic data."""
    import json
    import subprocess

    db = _tmp_db("sweep")
    store = MarketStore(db_path=db)
    try:
        # Seed scorecard rows directly.
        for i in range(60):
            conf = 0.5 + (i % 10) / 20
            correct = conf > 0.6
            store.conn.execute(
                "INSERT INTO scorecard (id, predicted_direction, actual_direction, "
                "predicted_confidence, was_correct, agent) VALUES (?, 'long', 'long', ?, ?, 'strategist')",
                [f"s{i}", conf, correct],
            )
    finally:
        # Close the connection BEFORE spawning the subprocess — DuckDB locks
        # the file, and the sweep script opens it read-only itself.
        store.close()

    try:
        out = subprocess.run(
            [sys.executable, "scripts/confidence_sweep.py", "--db", db, "--json"],
            capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert out.returncode == 0, out.stderr
        data = json.loads(out.stdout)
        assert data["sources"]["scorecard"] == 60
        assert len(data["results"]) > 10
        assert "recommendation" in data
    finally:
        if os.path.exists(db):
            os.remove(db)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL ROADMAP TESTS PASSED")
