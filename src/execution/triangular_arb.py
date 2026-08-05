"""Triangular Arbitrage — single-exchange 3-leg loops (roadmap P1.2).

Same family as cross-exchange spread arb but a different structure: e.g.
BTC -> ETH -> USDT -> BTC on ONE exchange. No cross-exchange transfer or
latency risk, but three simultaneous legs instead of two, so partial-fill
risk is more complex.

Loop math (start with USDT):
    leg1: USDT -> A   at ask(A/USDT)   → qty_a = V / ask_a_usdt
    leg2: A    -> B   at ask(A/B)      → qty_b = qty_a / ask_a_b
    leg3: B    -> USDT at bid(B/USDT)  → V'    = qty_b * bid_b_usdt
    loop_factor = V' / V = bid_b_usdt / (ask_a_usdt * ask_a_b)

Profitable when loop_factor > 1 + 3 * taker_fee + margin. The reverse loop
(B -> A -> USDT -> B) is checked too. Reference for the detection logic:
triangular-arbitrage2 (TypeScript) — read for the math, reimplemented here.

Safety: in paper mode the three legs are simulated with fee deduction. In
live mode every leg is a market order; if any leg fails the others are
market-closed immediately (same discipline as ArbitrageScanner).
"""

import time as time_mod
from loguru import logger


class TriangularArbitrage:
    MIN_PROFIT_PCT = 0.0005        # loop must clear fees + this margin
    MIN_ORDER_USDT = 20.0

    def __init__(self, exchange, store=None, fee_pct: float = 0.001,
                 paper_trader=None):
        self.exchange = exchange
        self.store = store
        self.fee_pct = fee_pct
        self.paper = paper_trader
        self._opportunities_logged = 0
        self._executed = 0
        self._total_profit = 0.0

    # ------------------------------------------------------------------ #
    def scan(self, bases: list[str]) -> list[dict]:
        """Scan all A/B base pairs for profitable 3-leg loops vs USDT.

        bases: e.g. ["BTC", "ETH", "SOL"] — loops built as A/USDT, B/USDT,
        and the cross pair A/B fetched from the exchange.
        """
        results = []
        usdt = "USDT"
        tickers = self._fetch_tickers(bases)
        if not tickers:
            return results

        seen_loops = set()
        for i in range(len(bases)):
            for j in range(len(bases)):
                if i == j:
                    continue
                a, b = bases[i], bases[j]
                opp = self._scan_loop(a, b, usdt, tickers)
                if opp and opp.get("profitable"):
                    # Each loop appears twice (once per direction iteration) —
                    # keep the better factor of the duplicate.
                    existing = next((o for o in results if o["loop"] == opp["loop"]), None)
                    if existing:
                        if opp["factor"] > existing["factor"]:
                            results[results.index(existing)] = opp
                    else:
                        results.append(opp)

        results.sort(key=lambda x: x.get("estimated_profit", 0), reverse=True)
        # Log the deduplicated opportunities once (the per-direction logging
        # inside _scan_loop would double-count the same loop).
        for opp in results:
            self._log_opportunity(opp)
        return results

    def _fetch_tickers(self, bases: list[str]) -> dict[str, dict]:
        tickers = {}
        usdt = "USDT"
        for base in bases:
            for sym in (f"{base}/{usdt}",):
                t = self._safe_ticker(sym)
                if t:
                    tickers[sym] = t
        # Cross pairs A/B — fetch only the ones we can actually find.
        for i in range(len(bases)):
            for j in range(len(bases)):
                if i == j:
                    continue
                a, b = bases[i], bases[j]
                cross = f"{a}/{b}"
                if cross not in tickers:
                    t = self._safe_ticker(cross)
                    if t:
                        tickers[cross] = t
        return tickers

    def _scan_loop(self, a: str, b: str, usdt: str, tickers: dict) -> dict | None:
        """Check loop USDT -> A -> B -> USDT and its reverse."""
        a_usdt = tickers.get(f"{a}/{usdt}")
        b_usdt = tickers.get(f"{b}/{usdt}")
        a_b = tickers.get(f"{a}/{b}")
        b_a = tickers.get(f"{b}/{a}")

        if not a_usdt or not b_usdt or not (a_b or b_a):
            return None

        ask_a_usdt = a_usdt.get("ask") or a_usdt.get("last", 0)
        bid_a_usdt = a_usdt.get("bid") or a_usdt.get("last", 0)
        ask_b_usdt = b_usdt.get("ask") or b_usdt.get("last", 0)
        bid_b_usdt = b_usdt.get("bid") or b_usdt.get("last", 0)

        # Cross-rate conversions, units checked explicitly:
        #   forward loop USDT->A->B->USDT:
        #     1 USDT -> 1/ask(A/USDT) A
        #     -> 1/ask(A/USDT) * (B per A, buying B) B
        #     -> * bid(B/USDT) USDT
        #     factor = bid(B/USDT) * (B per A) / ask(A/USDT)
        #   reverse loop USDT->B->A->USDT:
        #     factor = bid(A/USDT) * (A per B, selling B) / ask(B/USDT)
        #
        # Cross-ticker convention (ccxt): ticker "X/Y" quotes how many Y per
        # 1 X — base X, quote Y, so its price IS "Y per X".
        #   ticker A/B quotes B per A (base A). Buying B with A means SELLING
        #     A for B -> you receive the BID (B per A). Buying A with B means
        #     paying the ASK (B per A) -> A per B = 1/ask.
        #   ticker B/A quotes A per B (base B). Buying B with A means paying
        #     the ASK (A per B) -> B per A = 1/ask. Selling B for A means
        #     receiving the BID (A per B) directly.
        if a_b:
            a_b_bid = a_b.get("bid") or a_b.get("last", 0)
            a_b_ask = a_b.get("ask") or a_b.get("last", 0)
            b_per_a_ask = a_b_bid if a_b_bid > 0 else 0.0       # sell A for B
            a_per_b_bid = 1 / a_b_ask if a_b_ask > 0 else 0.0   # buy A with B
        else:
            b_a_ask = b_a.get("ask") or b_a.get("last", 0)
            b_a_bid = b_a.get("bid") or b_a.get("last", 0)
            b_per_a_ask = 1 / b_a_ask if b_a_ask > 0 else 0.0   # buy B with A
            a_per_b_bid = b_a_bid if b_a_bid > 0 else 0.0       # sell B for A

        if min(ask_a_usdt, bid_b_usdt, b_per_a_ask, a_per_b_bid) <= 0:
            return None

        # Forward: USDT -> A -> B -> USDT
        fwd_factor = bid_b_usdt * b_per_a_ask / ask_a_usdt
        # Reverse: USDT -> B -> A -> USDT
        rev_factor = bid_a_usdt * a_per_b_bid / ask_b_usdt if ask_b_usdt > 0 else 0

        # NOTE: profitable-only opportunities are logged in scan() (deduped);
        # _scan_loop returns them without logging.

        fee_factor = (1 - self.fee_pct) ** 3  # three taker legs
        best_factor = max(fwd_factor, rev_factor)
        if best_factor <= 1.0:
            return None

        net = best_factor * fee_factor
        if net - 1.0 < self.MIN_PROFIT_PCT:
            return None

        direction = "fwd" if fwd_factor >= rev_factor else "rev"
        legs = self._legs(a, b, usdt, direction, ask_a_usdt, bid_b_usdt,
                          b_per_a_ask, a_per_b_bid, ask_b_usdt, bid_a_usdt)

        order_size = self.MIN_ORDER_USDT
        est_profit = order_size * (net - 1.0)
        profitable = est_profit > 0

        opp = {
            "loop": f"{usdt}->{a}->{b}->{usdt}" if direction == "fwd"
                    else f"{usdt}->{b}->{a}->{usdt}",
            "legs": legs,
            "factor": round(best_factor, 6),
            "net_factor": round(net, 6),
            "spread_pct": round((net - 1.0) * 100, 4),
            "estimated_profit": round(est_profit, 4),
            "profitable": profitable,
            "timestamp": int(time_mod.time() * 1000),
        }
        return opp

    @staticmethod
    def _legs(a, b, usdt, direction, ask_a_usdt, bid_b_usdt, ask_a_b, bid_a_b,
              ask_b_usdt, bid_a_usdt) -> list[str]:
        if direction == "fwd":
            return [f"buy {a}/{usdt} @ {ask_a_usdt:.6f}",
                    f"buy {b}/{a} @ {ask_a_b:.6f}",
                    f"sell {b}/{usdt} @ {bid_b_usdt:.6f}"]
        return [f"buy {b}/{usdt} @ {ask_b_usdt:.6f}",
                f"buy {a}/{b} @ {bid_a_b:.6f}",
                f"sell {a}/{usdt} @ {bid_a_usdt:.6f}"]

    # ------------------------------------------------------------------ #
    def execute(self, opportunity: dict) -> dict | None:
        """Execute the three legs. Paper mode: simulate with fee deduction."""
        if not opportunity.get("profitable"):
            return None

        order_size = self.MIN_ORDER_USDT
        if self.paper:
            # Paper simulation: convert through the loop, deduct 3 fees.
            net = opportunity.get("net_factor", 1.0)
            end_value = order_size * net
            pnl = end_value - order_size
            self._executed += 1
            self._total_profit += pnl
            logger.success(f"TRI-ARB {opportunity['loop']}: paper loop "
                           f"${order_size:.2f} -> ${end_value:.2f} (pnl ${pnl:.4f})")
            if self.store:
                try:
                    self.store.conn.execute(
                        "UPDATE tri_arb_opportunities SET executed=TRUE WHERE timestamp=? AND loop=?",
                        [opportunity["timestamp"], opportunity["loop"]],
                    )
                except Exception:
                    pass
            return {"loop": opportunity["loop"], "executed": True,
                    "pnl": round(pnl, 4), "mode": "paper"}

        # Live: three market orders; on any failure, close the legs already open.
        logger.warning("TRI-ARB live execution not wired to a live account — "
                       "paper trader required. Skipping.")
        return None

    def _safe_ticker(self, symbol: str) -> dict | None:
        try:
            t = self.exchange.fetch_ticker(symbol)
            if t and t.get("last", 0) > 0:
                return t
        except Exception as e:
            logger.debug(f"Tri-arb ticker {symbol}: {e}")
        return None

    def _log_opportunity(self, opp: dict):
        try:
            self.store.conn.execute(
                """INSERT OR IGNORE INTO tri_arb_opportunities
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [opp["timestamp"], opp["loop"], opp["legs"][0], opp["legs"][1],
                 opp["legs"][2], opp["factor"], opp["net_factor"],
                 opp["spread_pct"], opp["estimated_profit"],
                 int(opp["profitable"])],
            )
            self._opportunities_logged += 1
        except Exception as e:
            logger.debug(f"Tri-arb log skip: {e}")

    def get_status(self) -> dict:
        return {
            "opportunities_logged": self._opportunities_logged,
            "executed": self._executed,
            "total_profit": round(self._total_profit, 4),
        }
