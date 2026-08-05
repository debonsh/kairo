"""Systematic alpha discovery (roadmap P1.3).

Instead of hand-coding indicator strategy #6/#7/#8, generate candidate
``evaluate()``-shaped strategies from a small grammar of indicator
primitives, score them on historical candles, and feed the survivors through
the SAME validation pipeline the hand-coded strategies use (walk-forward /
meta-labeling / shadow mode). No new execution infrastructure needed — the
candidates slot into the existing SignalEngine.

References: AlphaGen (RL formulaic alpha) and Genetic-Alpha (genetic
programming for factors) — research-grade ideas, reimplemented here as a
lightweight generator + scorer over the store's candle data.

Usage:
    python -m src.backtest.alpha_search --symbols BTC/USDT,ETH/USDT --n 40 --keep 5
"""

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.pipeline.store import MarketStore


# ---------------------------------------------------------------------- #
# Indicator primitives — computed from a candle matrix, produce a per-bar
# boolean signal. Each is a pure function (closes, highs, lows, volumes).
# ---------------------------------------------------------------------- #
def _sma(closes: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(closes), np.nan)
    if len(closes) >= n:
        kernel = np.ones(n) / n
        valid = np.convolve(closes, kernel, mode="valid")
        out[n - 1:] = valid
    return out


def prim_close_above_sma(closes, highs, lows, vols, n=20):
    sma = _sma(closes, n)
    return np.where(np.isnan(sma), 0, (closes > sma).astype(float))


def prim_rsi_oversold(closes, highs, lows, vols, period=14):
    deltas = np.diff(closes, prepend=closes[0])
    gains = np.maximum(deltas, 0)
    losses = np.maximum(-deltas, 0)
    ag = _sma(gains, period)
    al = _sma(losses, period)
    rsi = 100 - 100 / (1 + np.where(al == 0, 1e-9, ag / np.where(al == 0, 1e-9, al)))
    return (rsi < 30).astype(float)


def prim_rsi_overbought(closes, highs, lows, vols, period=14):
    deltas = np.diff(closes, prepend=closes[0])
    gains = np.maximum(deltas, 0)
    losses = np.maximum(-deltas, 0)
    ag = _sma(gains, period)
    al = _sma(losses, period)
    rsi = 100 - 100 / (1 + np.where(al == 0, 1e-9, ag / np.where(al == 0, 1e-9, al)))
    return (rsi > 70).astype(float)


def prim_breakout(closes, highs, lows, vols, n=20):
    out = np.zeros(len(closes))
    for i in range(n, len(closes)):
        out[i] = 1 if closes[i] > np.max(highs[i - n:i]) else 0
    return out


def prim_volume_spike(closes, highs, lows, vols, n=20):
    out = np.zeros(len(closes))
    for i in range(n, len(closes)):
        avg = np.mean(vols[i - n:i])
        out[i] = 1 if avg > 0 and vols[i] > avg * 1.5 else 0
    return out


def prim_bb_lower(closes, highs, lows, vols, n=20):
    sma = _sma(closes, n)
    std = np.zeros(len(closes))
    for i in range(n, len(closes)):
        std[i] = np.std(closes[i - n:i])
    return np.where((sma - 2 * std) > 0, (closes <= (sma - 2 * std)).astype(float), 0)


PRIMITIVES = {
    "close_above_sma": prim_close_above_sma,
    "rsi_oversold": prim_rsi_oversold,
    "rsi_overbought": prim_rsi_overbought,
    "breakout": prim_breakout,
    "volume_spike": prim_volume_spike,
    "bb_lower": prim_bb_lower,
}


# ---------------------------------------------------------------------- #
# Candidate grammar: an expression is AND/OR of two primitives, plus a
# direction (long when true, short when true, or contrarian).
# ---------------------------------------------------------------------- #
def random_candidate(rng: random.Random) -> dict:
    names = list(PRIMITIVES)
    p1, p2 = rng.sample(names, 2)
    op = rng.choice(["AND", "OR"])
    direction = rng.choice(["long", "short", "contrarian"])
    return {
        "name": f"alpha_{p1}_{op}_{p2}_{direction}",
        "p1": p1, "p2": p2, "op": op, "direction": direction,
    }


def eval_candidate(cand: dict, candles: list) -> np.ndarray:
    """Evaluate a candidate over candles → per-bar {-1,0,1} signal."""
    if len(candles) < 60:
        return np.zeros(len(candles))
    closes = np.array([c[4] for c in candles], dtype=float)
    highs = np.array([c[2] for c in candles], dtype=float)
    lows = np.array([c[3] for c in candles], dtype=float)
    vols = np.array([c[5] for c in candles], dtype=float)

    s1 = PRIMITIVES[cand["p1"]](closes, highs, lows, vols)
    s2 = PRIMITIVES[cand["p2"]](closes, highs, lows, vols)
    if cand["op"] == "AND":
        raw = np.minimum(s1, s2)
    else:
        raw = np.maximum(s1, s2)

    if cand["direction"] == "short":
        raw = -raw
    elif cand["direction"] == "contrarian":
        raw = -raw  # fade the primitive condition

    signal = np.zeros(len(raw))
    signal[raw > 0] = 1
    signal[raw < 0] = -1
    return signal


def score_candidate(cand: dict, candles: list, fee_pct: float = 0.001) -> dict:
    """Walk-forward-ish score: signal → next-bar return, net of fees."""
    signal = eval_candidate(cand, candles)
    closes = np.array([c[4] for c in candles], dtype=float)
    if len(signal) < 60:
        return {"name": cand["name"], "sharpe": 0, "total_return_pct": 0,
                "trades": 0, "win_rate": 0, "valid": False}

    # Trade when signal flips to non-zero; exit when it flips to the opposite.
    rets = []
    position = 0
    entry = None
    for i in range(60, len(signal) - 1):
        nxt = signal[i]
        if position == 0 and nxt != 0:
            position = nxt
            entry = closes[i]
        elif position != 0 and (nxt == -position or nxt == 0):
            if entry and entry > 0:
                r = (closes[i + 1] - entry) / entry * position - fee_pct * 2
                rets.append(r)
            position = 0
            entry = None

    if not rets:
        return {"name": cand["name"], "sharpe": 0, "total_return_pct": 0,
                "trades": 0, "win_rate": 0, "valid": False}

    rets = np.array(rets)
    sharpe = (rets.mean() / rets.std() * np.sqrt(365 * 4)) if rets.std() > 0 else 0
    return {
        "name": cand["name"],
        "sharpe": round(float(sharpe), 3),
        "total_return_pct": round(float(rets.sum() * 100), 2),
        "trades": len(rets),
        "win_rate": round(float((rets > 0).mean() * 100), 1),
        "valid": True,
    }


# ---------------------------------------------------------------------- #
def search(store: MarketStore, symbols: list[str], n_candidates: int = 40,
           keep: int = 5, seed: int = 42, max_candles: int = 3000) -> list[dict]:
    """Generate + score candidates across symbols; return top-`keep`."""
    rng = random.Random(seed)
    candidates = [random_candidate(rng) for _ in range(n_candidates)]

    # Load candle history once per symbol (reuse across candidates).
    history = {}
    for sym in symbols:
        rows = store.get_candles("bybit", sym, "15m", limit=max_candles)
        candles = [[r["timestamp"], r["open"], r["high"], r["low"], r["close"], r["volume"]]
                   for r in rows]
        if len(candles) >= 100:
            history[sym] = candles

    if not history:
        logger.warning("Alpha search: no usable candle history in store")
        return []

    scored = []
    for cand in candidates:
        scores = [score_candidate(cand, history[sym]) for sym in history]
        valid = [s for s in scores if s["valid"]]
        if not valid:
            continue
        agg = {
            "name": cand["name"],
            "sharpe": round(float(np.mean([s["sharpe"] for s in valid])), 3),
            "total_return_pct": round(float(np.mean([s["total_return_pct"] for s in valid])), 2),
            "trades": int(np.mean([s["trades"] for s in valid])),
            "win_rate": round(float(np.mean([s["win_rate"] for s in valid])), 1),
            "p1": cand["p1"], "p2": cand["p2"], "op": cand["op"], "direction": cand["direction"],
            "symbols": len(valid),
        }
        scored.append(agg)

    scored.sort(key=lambda s: s["sharpe"], reverse=True)
    return scored[:keep]


def main():
    ap = argparse.ArgumentParser(description="Alpha candidate search (P1.3)")
    ap.add_argument("--symbols", default="BTC/USDT,ETH/USDT,SOL/USDT")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--keep", type=int, default=5)
    ap.add_argument("--db", default="data/market.db")
    ap.add_argument("--out", default="data/alpha_candidates.json")
    args = ap.parse_args()

    store = MarketStore(db_path=args.db)
    try:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
        top = search(store, symbols, n_candidates=args.n, keep=args.keep)
        if not top:
            logger.warning("No valid candidates — need >=100 candles per symbol")
            return
        logger.info(f"Top {len(top)} alpha candidates by mean Sharpe:")
        for t in top:
            logger.info(f"  {t['name']:45s} Sharpe={t['sharpe']:.3f} "
                        f"ret={t['total_return_pct']:+.2f}% trades={t['trades']} "
                        f"WR={t['win_rate']}%")
        Path(args.out).write_text(json.dumps(top, indent=2))
        logger.info(f"Candidates written to {args.out}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
