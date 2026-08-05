"""Concurrency regression test for MarketStore.

Regression for the transient ``IndexError: tuple index out of range`` in
``/candles``: a single DuckDB connection shared across threads (trading
loop writes + API reads) is undefined behavior. MarketStore now hands each
thread its own connection, so concurrent reads/writes must never error or
return malformed rows.
"""
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline.store import MarketStore


def _tmp_db(name: str) -> str:
    path = os.path.join(os.environ.get("TEMP", "/tmp"), f"kairo_test_{name}.db")
    if os.path.exists(path):
        os.remove(path)
    return path


def _hammer_readers(store, symbol: str, errors: list, stop: threading.Event):
    """Reader threads run the exact query /candles uses, in a loop."""
    while not stop.is_set():
        try:
            rows = store.conn.execute(
                "SELECT timestamp, open, high, low, close, volume FROM candles "
                "WHERE exchange='bybit' AND symbol=? AND timeframe='1h' "
                "ORDER BY timestamp DESC LIMIT 150",
                [symbol],
            ).fetchall()
            for r in rows:
                # A garbled row (the pre-fix failure mode) has < 6 fields.
                if len(r) != 6:
                    errors.append(f"garbled row len={len(r)}: {r[:3]}")
                    return
        except Exception as e:
            errors.append(f"{type(e).__name__}: {e}")
            return
    return


def test_concurrent_read_write_no_garbled_rows():
    db = _tmp_db("concurrency")
    store = MarketStore(db_path=db)
    symbol = "BTC/USDT"
    try:
        # Seed some candles so reads have data.
        t0 = int(time.time() * 1000) - 2000 * 60_000
        store.insert_candles("bybit", symbol, "1h", [
            [t0 + i * 60_000, 100, 101, 99, 100 + i * 0.1, 1000] for i in range(50)
        ])

        errors: list = []
        stop = threading.Event()

        def writer():
            # Trading-loop style: continuous upserts while readers query.
            i = 0
            while not stop.is_set():
                try:
                    store.insert_candles("bybit", symbol, "1h", [
                        [t0 + (2000 + i) * 60_000, 100, 102, 98, 101, 1000]
                    ])
                except Exception as e:
                    errors.append(f"writer {type(e).__name__}: {e}")
                    return
                i += 1
                time.sleep(0.001)

        threads = [threading.Thread(target=writer)]
        threads += [threading.Thread(target=_hammer_readers, args=(store, symbol, errors, stop))
                    for _ in range(3)]

        for t in threads:
            t.start()
        time.sleep(1.0)  # let them collide
        stop.set()
        for t in threads:
            t.join(timeout=5)

        assert not errors, f"Concurrent store access failed: {errors[:5]}"

        # Writer's rows are visible to the reader threads' connection.
        count = store.conn.execute(
            "SELECT COUNT(*) FROM candles WHERE symbol=?", [symbol]
        ).fetchone()[0]
        assert count >= 50, f"Expected >=50 candles, got {count}"
    finally:
        stop.set()
        store.close()
        if os.path.exists(db):
            os.remove(db)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL STORE CONCURRENCY TESTS PASSED")
