"""Sweep ``min_confidence`` across a range (default 0.50-0.70) against the
live/paper journal and report the threshold the DATA supports — instead of
leaving the fixed 0.55 guess in place.

Roadmap P0.3: "Sweep min_confidence across a reasonable range (e.g. 0.50-0.70)
against your existing journal using Calibrator, and pick the value the data
supports instead of the current fixed 0.55."

Usage:
    python scripts/confidence_sweep.py                      # live DB (or newest backup if locked)
    python scripts/confidence_sweep.py --db data/backups/market_*.ddb
    python scripts/confidence_sweep.py --lo 0.50 --hi 0.70 --step 0.01

Data used, in priority order:
  1. ``scorecard`` rows (predicted_confidence + was_correct) — the Calibrator's
     own input, no join needed.
  2. ``agent_decisions`` JSON (signal confidence) joined to closed ``trades``
     (pnl) by symbol + time proximity — reconstructs per-trade confidence.

The report always prints the sample size behind each threshold; below 30
matched samples the number is a hint, not a verdict (same discipline
FuturesGate applies to itself).
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb

CURRENT_DEFAULT = 0.55
MIN_SAMPLES_FOR_VERDICT = 30


def pick_db(path: str | None) -> str:
    """Use the requested DB, or the live DB, or fall back to the newest backup
    when the live DB is locked by a running bot process."""
    if path:
        return path
    candidates = ["data/market.db"]
    backups = sorted(Path("data/backups").glob("market_*.ddb"), reverse=True)
    candidates += [str(b) for b in backups]
    for db in candidates:
        try:
            con = duckdb.connect(db, read_only=True)
            con.execute("SELECT 1 FROM trades LIMIT 1").fetchone()
            con.close()
            return db
        except Exception:
            continue
    raise SystemExit("No readable DB found (live DB locked and no backups?)")


def load_scorecard_rows(con) -> list[dict]:
    try:
        rows = con.execute(
            "SELECT predicted_confidence, was_correct FROM scorecard "
            "WHERE predicted_confidence IS NOT NULL"
        ).fetchall()
        return [{"confidence": float(r[0]), "was_correct": bool(r[1])} for r in rows]
    except Exception:
        return []


def load_decision_trade_pairs(con) -> list[dict]:
    """Join agent_decisions (signal confidence) to closed trades (pnl) by
    symbol + decision-within-15min-before-entry."""
    pairs = []
    try:
        decisions = con.execute(
            "SELECT symbol, timestamp, decision FROM agent_decisions"
        ).fetchall()
        trades = con.execute(
            "SELECT symbol, entry_time, pnl FROM trades "
            "WHERE status='closed' AND pnl IS NOT NULL"
        ).fetchall()
    except Exception:
        return pairs

    trades_by_sym = {}
    for sym, entry_ms, pnl in trades:
        trades_by_sym.setdefault(sym, []).append((entry_ms, pnl))

    for sym, ts, decision_json in decisions:
        if not decision_json:
            continue
        try:
            decision = json.loads(decision_json) if isinstance(decision_json, str) else decision_json
        except (json.JSONDecodeError, TypeError):
            continue
        signal = decision.get("signal") or {}
        confidence = signal.get("confidence")
        if confidence is None:
            continue
        ts_ms = int(ts.timestamp() * 1000) if hasattr(ts, "timestamp") else int(ts)
        # Match to a trade entered within 15 minutes after the decision.
        for entry_ms, pnl in trades_by_sym.get(sym, []):
            if 0 <= entry_ms - ts_ms <= 15 * 60 * 1000:
                pairs.append({"confidence": float(confidence), "pnl": float(pnl)})
                break
    return pairs


def sweep(rows: list[dict], lo: float, hi: float, step: float) -> list[dict]:
    results = []
    for t in [round(lo + i * step, 3) for i in range(int((hi - lo) / step) + 1)]:
        passed = [r for r in rows if r["confidence"] >= t]
        if not passed:
            results.append({"threshold": t, "n": 0})
            continue
        pnls = [r.get("pnl") for r in passed]
        wins = sum(1 for r in passed if r.get("was_correct", r.get("pnl", 0) > 0))
        total_pnl = sum(p for p in pnls if p is not None) if any(p is not None for p in pnls) else None
        results.append({
            "threshold": t,
            "n": len(passed),
            "win_rate": round(wins / len(passed) * 100, 1),
            "total_pnl": round(total_pnl, 2) if total_pnl is not None else None,
            "avg_pnl": round(total_pnl / len(passed), 2) if total_pnl is not None else None,
        })
    return results


def recommend(results: list[dict]) -> str:
    valid = [r for r in results if r.get("n", 0) >= MIN_SAMPLES_FOR_VERDICT and r.get("avg_pnl") is not None]
    if not valid:
        return ("INSUFFICIENT DATA — no threshold has >= "
                f"{MIN_SAMPLES_FOR_VERDICT} matched samples. "
                "Keep 0.55 until the journal grows.")
    # Pick the threshold maximizing avg_pnl; tie-break on sample size.
    best = max(valid, key=lambda r: (r["avg_pnl"], r["n"]))
    delta = best["avg_pnl"] - (next((r["avg_pnl"] for r in valid if abs(r["threshold"] - CURRENT_DEFAULT) < 1e-9), 0) or 0)
    if best["threshold"] != CURRENT_DEFAULT and delta > 0:
        return (f"Data supports {best['threshold']:.2f} (avg_pnl "
                f"${best['avg_pnl']:.2f}, n={best['n']}) vs current "
                f"{CURRENT_DEFAULT} — delta ${delta:.2f}/trade.")
    return (f"Data supports keeping {CURRENT_DEFAULT} — best is "
            f"{best['threshold']:.2f} (avg_pnl ${best['avg_pnl']:.2f}, n={best['n']}).")


def main():
    ap = argparse.ArgumentParser(description="Sweep min_confidence against the journal")
    ap.add_argument("--db", default=None)
    ap.add_argument("--lo", type=float, default=0.50)
    ap.add_argument("--hi", type=float, default=0.70)
    ap.add_argument("--step", type=float, default=0.01)
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = ap.parse_args()

    db = pick_db(args.db)
    con = duckdb.connect(db, read_only=True)
    try:
        scorecard = load_scorecard_rows(con)
        pairs = load_decision_trade_pairs(con)
    finally:
        con.close()

    if not scorecard and not pairs:
        print("No usable journal data (scorecard empty, no decision/trade matches).")
        return

    results = sweep(scorecard if scorecard else pairs, args.lo, args.hi, args.step)

    if args.json:
        print(json.dumps({
            "db": db,
            "sources": {"scorecard": len(scorecard), "decision_trade_pairs": len(pairs)},
            "results": results,
            "recommendation": recommend(results),
        }, indent=2))
        return

    print(f"DB: {db}")
    print(f"Sources: {len(scorecard)} scorecard rows, {len(pairs)} decision-trade matches")

    print(f"\n{'threshold':>9} {'n':>5} {'win%':>6} {'total_pnl':>10} {'avg_pnl':>9}")
    print("-" * 48)
    for r in results:
        if r.get("n", 0) == 0:
            print(f"{r['threshold']:>9.2f} {0:>5} {'—':>6}")
            continue
        print(f"{r['threshold']:>9.2f} {r['n']:>5} {r['win_rate']:>6.1f} "
              f"{(r['total_pnl'] if r['total_pnl'] is not None else 0):>10.2f} "
              f"{(r['avg_pnl'] if r['avg_pnl'] is not None else 0):>9.2f}")
    print("-" * 48)
    print(recommend(results))


if __name__ == "__main__":
    main()
