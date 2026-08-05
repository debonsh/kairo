"""Fill validation for SpreadOptimizer (roadmap P2.2).

``SpreadOptimizer`` learns fill rates per coin from live order feedback. The
problem: it's easy to be subtly wrong about "will this limit order actually
fill where I think it will" without realistic backtesting. This module
simulates queue position and latency against the tick/candle history stored
in DuckDB and reports the simulated fill rate at each offset — so the
optimizer's learned assumptions can be validated instead of trusted.

Model (lightweight, no hftbacktest dependency):
  - A limit order placed at ``offset_pct`` from the last close.
  - It fills when the market trades through the limit level (intrabar high
    crosses a buy limit; intrabar low crosses a sell limit).
  - Queue position is proxied by time-in-market: a limit that is only
    momentarily crossed (touched by a wick) is treated as "queue ahead of
    us" — we only count fills when the close is THROUGH the level, i.e. the
    move persists, which is the conservative bound.
  - Latency penalty: the order's effective level is shifted by ``latency_ms``
    of price movement (vol-scaled), degrading fills on fast moves.

Returns the empirical fill rate curve per offset so SpreadOptimizer's
learned rates can be compared against it.
"""

import numpy as np
from loguru import logger


class FillSimulator:
    def __init__(self, fee_pct: float = 0.001, latency_ms: float = 200.0):
        self.fee_pct = fee_pct
        self.latency_ms = latency_ms

    @staticmethod
    def simulate(store, symbol: str, timeframe: str = "15m",
                 offsets_pct: list[float] | None = None,
                 latency_ms: float = 200.0, lookback_bars: int = 1000) -> dict:
        """Simulate limit fill rates for a symbol across offset levels.

        offsets_pct: e.g. [0.05, 0.1, 0.2, 0.3, 0.5] — how far from the close
        the limit is placed (half-spread style).
        """
        if offsets_pct is None:
            offsets_pct = [0.05, 0.1, 0.2, 0.3, 0.5]

        rows = store.get_candles("bybit", symbol, timeframe, limit=lookback_bars)
        if len(rows) < 100:
            logger.warning(f"FillSim: not enough {symbol} candles ({len(rows)})")
            return {"symbol": symbol, "offsets": offsets_pct,
                    "fill_rates": [], "bars": len(rows)}

        highs = np.array([r["high"] for r in rows], dtype=float)
        lows = np.array([r["low"] for r in rows], dtype=float)
        closes = np.array([r["close"] for r in rows], dtype=float)

        # Vol-scaled latency penalty: how far price can move in latency_ms.
        rets = np.abs(np.diff(closes) / np.maximum(closes[:-1], 1e-9))
        vol_per_bar = float(np.percentile(rets, 50)) if len(rets) else 0.001
        latency_frac = latency_ms / (timeframe_ms(timeframe))
        latency_shift = vol_per_bar * latency_frac

        fill_rates = []
        for offset in offsets_pct:
            buys_filled = 0
            sells_filled = 0
            n = len(rows) - 1
            for i in range(1, n):
                prev_close = closes[i - 1]
                # Buy limit below prev close; sell limit above.
                buy_level = prev_close * (1 - offset / 100)
                sell_level = prev_close * (1 + offset / 100)
                # Conservative fill: only when the CLOSE is through the level
                # (persistent move), not a wick touch. Latency shifts level.
                if closes[i] <= buy_level * (1 - latency_shift):
                    buys_filled += 1
                if closes[i] >= sell_level * (1 + latency_shift):
                    sells_filled += 1

            total = 2 * n
            fill_rates.append(round((buys_filled + sells_filled) / total * 100, 2))

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "latency_ms": latency_ms,
            "offsets": offsets_pct,
            "fill_rates": fill_rates,
            "bars": len(rows),
        }

    @staticmethod
    def compare_with_optimizer(sim_result: dict, optimizer_learned: dict) -> dict:
        """Compare simulated fill rates vs SpreadOptimizer's learned rates."""
        report = []
        for off, sim in zip(sim_result["offsets"], sim_result["fill_rates"]):
            learned = optimizer_learned.get(off)
            report.append({
                "offset_pct": off,
                "simulated_fill_rate": sim,
                "learned_fill_rate": learned,
                "gap_pct": round(sim - learned, 2) if learned is not None else None,
            })
        return {"symbol": sim_result["symbol"], "report": report}


def timeframe_ms(tf: str) -> float:
    unit = tf[-1]
    val = int(tf[:-1]) if tf[:-1].isdigit() else 1
    mult = {"m": 60_000, "h": 3_600_000, "d": 86_400_000}.get(unit, 60_000)
    return val * mult


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from src.pipeline.store import MarketStore

    store = MarketStore(db_path="data/market.db")
    result = FillSimulator.simulate(store, "BTC/USDT", offsets_pct=[0.05, 0.1, 0.2, 0.3, 0.5])
    print(result)
    store.close()
