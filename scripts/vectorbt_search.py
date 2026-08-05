"""vectorbt parameter search (roadmap P3.1).

Between walk-forward validation, purged k-fold, meta-label retraining and
shadow-mode promotion, the research loop runs a lot of repeated backtests.
vectorbt is numba-accelerated and vectorized — much faster than the
event-driven engine for the SEARCH phase. Use this script to find candidate
parameters, then confirm the survivors with the event-driven
``BacktestEngine`` before shadow mode.

Usage:
    python scripts/vectorbt_search.py --symbol BTC/USDT --db data/market.db
    python scripts/vectorbt_search.py --fast 5 60 --slow 10 120 --n 40
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FREQ = "15min"  # vectorbt frequency string — set from --timeframe in main()


def load_candles(store, symbol: str, timeframe: str = "15m", limit: int = 3000) -> dict:
    rows = store.get_candles("bybit", symbol, timeframe, limit=limit)
    if len(rows) < 100:
        raise SystemExit(f"Not enough candles for {symbol}: {len(rows)}")
    return {
        "open": np.array([r["open"] for r in rows], dtype=float),
        "high": np.array([r["high"] for r in rows], dtype=float),
        "low": np.array([r["low"] for r in rows], dtype=float),
        "close": np.array([r["close"] for r in rows], dtype=float),
        "volume": np.array([r["volume"] for r in rows], dtype=float),
        "timestamp": np.array([r["timestamp"] for r in rows], dtype=np.int64),
    }


def sma_cross_sweep(data: dict, fast_range, slow_range, fee_pct: float = 0.001) -> list[dict]:
    """Vectorized SMA-cross parameter sweep via vectorbt."""
    import vectorbt as vbt

    close = data["close"]
    results = []
    for fast in fast_range:
        for slow in slow_range:
            if fast >= slow:
                continue
            fast_sma = vbt.MA.run(close, fast).ma
            slow_sma = vbt.MA.run(close, slow).ma
            entries = (fast_sma > slow_sma) & (fast_sma.shift(1) <= slow_sma.shift(1))
            exits = (fast_sma < slow_sma) & (fast_sma.shift(1) >= slow_sma.shift(1))
            pf = vbt.Portfolio.from_signals(
                close, entries, exits, freq=FREQ, fees=fee_pct,
                init_cash=5000.0, size=0.02,
            )
            results.append({
                "fast": fast, "slow": slow,
                "total_return": round(float(pf.total_return()), 4),
                "sharpe": round(float(pf.sharpe_ratio()), 3),
                "trades": int(pf.trades.count()),
                "win_rate": round(float(_safe_win_rate(pf)) * 100, 1),
            })
    results.sort(key=lambda r: r["sharpe"], reverse=True)
    return results


def _safe_win_rate(pf) -> float:
    """vectorbt 1.x returns a scalar from win_rate(); 0.x returned a Series."""
    wr = pf.trades.win_rate()
    if hasattr(wr, "iloc") or hasattr(wr, "__getitem__"):
        try:
            return float(wr.iloc[0]) if hasattr(wr, "iloc") else float(wr[0])
        except (IndexError, TypeError):
            return 0.0
    return float(wr)


def rsi_sweep(data: dict, periods, oversold_range, overbought_range,
              fee_pct: float = 0.001) -> list[dict]:
    import vectorbt as vbt

    close = data["close"]
    results = []
    for period in periods:
        rsi = vbt.RSI.run(close, period).rsi
        for os_ in oversold_range:
            for ob_ in overbought_range:
                if os_ >= ob_:
                    continue
                entries = rsi < os_
                exits = rsi > ob_
                pf = vbt.Portfolio.from_signals(
                    close, entries, exits, freq=FREQ, fees=fee_pct,
                    init_cash=5000.0, size=0.02,
                )
                results.append({
                    "period": period, "oversold": os_, "overbought": ob_,
                    "total_return": round(float(pf.total_return()), 4),
                    "sharpe": round(float(pf.sharpe_ratio()), 3),
                    "trades": int(pf.trades.count()),
                    "win_rate": round(float(_safe_win_rate(pf)) * 100, 1),
                })
    results.sort(key=lambda r: r["sharpe"], reverse=True)
    return results


def main():
    ap = argparse.ArgumentParser(description="vectorbt parameter search (P3.1)")
    ap.add_argument("--symbol", default="BTC/USDT")
    ap.add_argument("--db", default="data/market.db")
    ap.add_argument("--timeframe", default="15m")
    ap.add_argument("--limit", type=int, default=3000)
    ap.add_argument("--fast", nargs=2, type=int, default=[5, 30], help="fast SMA range")
    ap.add_argument("--slow", nargs=2, type=int, default=[20, 90], help="slow SMA range")
    ap.add_argument("--strategy", choices=["sma", "rsi"], default="sma")
    args = ap.parse_args()
    from src.pipeline.store import MarketStore
    global FREQ
    FREQ = {"15m": "15min", "1h": "60min", "4h": "240min", "1d": "1D"}.get(args.timeframe, "15min")
    store = MarketStore(db_path=args.db)
    try:
        data = load_candles(store, args.symbol, args.timeframe, args.limit)
        fast_range = range(args.fast[0], args.fast[1] + 1, 5)
        slow_range = range(args.slow[0], args.slow[1] + 1, 10)

        if args.strategy == "sma":
            results = sma_cross_sweep(data, fast_range, slow_range)
            header = "fast  slow"
        else:
            results = rsi_sweep(data, periods=range(5, 21, 5),
                                oversold_range=range(20, 41, 5),
                                overbought_range=range(60, 81, 5))
            header = "per  os  ob"

        print(f"vectorbt sweep — {args.symbol} {args.timeframe} ({len(data['close'])} bars)")
        print(f"{header:>14} {'ret%':>8} {'sharpe':>7} {'trades':>7} {'win%':>6}")
        for r in results[:10]:
            if args.strategy == "sma":
                label = f"{r['fast']:>4} {r['slow']:>4}"
            else:
                label = f"{r['period']:>3} {r['oversold']:>3} {r['overbought']:>3}"
            print(f"{label:>14} {r['total_return']*100:>8.2f} {r['sharpe']:>7.2f} "
                  f"{r['trades']:>7} {r['win_rate']:>6.1f}")
        print("\nTop params above are SEARCH-phase candidates — confirm with the "
              "event-driven BacktestEngine before shadow mode.")
    finally:
        store.close()


if __name__ == "__main__":
    main()
