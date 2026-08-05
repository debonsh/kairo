"""Joint position sizing (roadmap P2.1).

``RiskManagerAgent`` sizes per-signal (vol-target, Kelly, max-allowed) and
then applies a correlation CAP as an afterthought. This module solves for
position sizes across the whole portfolio AT ONCE with a convex optimizer
(cvxpy), properly accounting for correlation between simultaneously-held
positions. Kelly/vol-targeting still define the per-position upper bounds the
optimizer works within — this is an extension of the existing correlation-cap
logic, not a replacement for it.

Correlation matrix: computed from historical candle returns in the store
(per-symbol, aligned on 15m timestamps). If cvxpy is unavailable or the
matrix is degenerate, falls back to the per-signal sizing already in place
(never blocks a trade).
"""

import numpy as np
from loguru import logger

try:
    import cvxpy as cp
    CVXPY_AVAILABLE = True
except ImportError:
    CVXPY_AVAILABLE = False


class JointPositionSizer:
    def __init__(self, store, risk_free: float = 0.0):
        self.store = store
        self.risk_free = risk_free
        # Last solve diagnostics — surfaced on the dashboard (roadmap P2.1)
        self.last_solve: dict = {"solved": False, "reason": "never run"}

    @staticmethod
    def available() -> bool:
        return CVXPY_AVAILABLE

    def get_status(self) -> dict:
        """Dashboard-facing status: whether cvxpy is available + the last solve."""
        return {
            "available": CVXPY_AVAILABLE,
            "last_solve": self.last_solve,
        }

    # ------------------------------------------------------------------ #
    def correlation_matrix(self, symbols: list[str], lookback_bars: int = 500) -> np.ndarray | None:
        """Pairwise return correlation from aligned 15m candle closes."""
        if not symbols or len(symbols) < 2:
            return None
        series = {}
        for sym in symbols:
            rows = self.store.get_candles("bybit", sym, "15m", limit=lookback_bars)
            closes = np.array([r["close"] for r in rows], dtype=float)
            if len(closes) < 60:
                return None
            rets = np.diff(np.log(np.maximum(closes, 1e-9)))
            series[sym] = (rows[-1]["timestamp"], rets)

        # Align by timestamp: use the common tail window across symbols.
        min_len = min(len(rets) for _, rets in series.values())
        if min_len < 30:
            return None
        ret_matrix = np.column_stack([rets[-min_len:] for _, rets in series.values()])
        std = ret_matrix.std(axis=0)
        if np.any(std < 1e-12):
            return None
        corr = np.corrcoef(ret_matrix, rowvar=False)
        if np.any(np.isnan(corr)):
            return None
        # Regularize — a raw sample corr can be non-PSD; shrink toward identity.
        return 0.9 * corr + 0.1 * np.eye(len(symbols))

    # ------------------------------------------------------------------ #
    def solve(self, symbols: list[str], expected_rets: list[float],
              size_caps_usdt: list[float], budget_usdt: float,
              max_single_pct: float = 0.2) -> dict:
        """Maximize expected return subject to portfolio risk + per-position caps.

        args:
          symbols:        position symbols (open + candidate)
          expected_rets:  per-symbol expected return proxy (e.g. meta-confidence)
          size_caps_usdt: per-symbol max notional (from Kelly/vol-target caps)
          budget_usdt:    total capital to allocate
          max_single_pct: hard cap on any single weight (fraction of budget)

        Returns {symbols, weights, notional_usdt, solved: bool}.
        """
        n = len(symbols)
        if not CVXPY_AVAILABLE or n < 2:
            return {"solved": False, "reason": "cvxpy unavailable or single position"}

        corr = self.correlation_matrix(symbols)
        if corr is None:
            return {"solved": False, "reason": "no correlation data"}

        w = cp.Variable(n)
        mu = np.array(expected_rets, dtype=float)
        Sigma = np.array(corr, dtype=float)
        # Risk = sqrt(w' Σ w) — minimize variance-ish, penalized by -μ'w.
        risk = cp.quad_form(w, Sigma)
        objective = cp.Maximize(mu @ w - 0.5 * risk)
        constraints = [
            w >= 0,
            cp.sum(w) <= 1.0,
            w <= max_single_pct,
        ]
        prob = cp.Problem(objective, constraints)
        try:
            prob.solve(solver=cp.CLARABEL)
        except Exception:
            try:
                prob.solve()
            except Exception as e:
                logger.debug(f"Joint sizer solve failed: {e}")
                return {"solved": False, "reason": f"solve failed: {e}"}

        if w.value is None or not np.isfinite(w.value).all():
            return {"solved": False, "reason": "no feasible solution"}

        weights = np.clip(w.value, 0, None)
        # Scale to per-position dollar caps, then to budget.
        caps = np.array(size_caps_usdt, dtype=float)
        cap_scaled = np.minimum(weights * budget_usdt, caps)
        total = cap_scaled.sum()
        if total <= 0:
            return {"solved": False, "reason": "zero allocation"}

        # Re-normalize within budget (respecting caps means we may allocate less).
        notional = cap_scaled * (budget_usdt / max(total, budget_usdt))
        return {
            "solved": True,
            "symbols": symbols,
            "weights": np.round(weights, 4).tolist(),
            "notional_usdt": np.round(notional, 2).tolist(),
            "expected_return": round(float(mu @ weights), 4),
            "portfolio_risk": round(float(np.sqrt(weights @ Sigma @ weights)), 4),
        }

    # ------------------------------------------------------------------ #
    def size_with_open(self, candidate: dict, open_trades: list[dict],
                       portfolio: dict, market_data: dict, size_usdt: float) -> dict:
        """Size a candidate position jointly with open positions.

        Returns a dict with ``adjusted_usdt`` (the candidate's final size) and
        diagnostics. Falls back to ``size_usdt`` unchanged when joint solving
        isn't possible.
        """
        open_symbols = [t.get("symbol") for t in open_trades if t.get("symbol")]
        symbols = open_symbols + [candidate.get("symbol")]
        if len(symbols) < 2:
            self.last_solve = {"solved": False, "reason": "no correlated positions to size against"}
            return {"adjusted_usdt": size_usdt, "joint": False,
                    "reason": "no correlated positions to size against"}

        # Expected return proxy: meta-confidence where available, else the
        # direction + confidence sign.
        expected_rets = []
        for sym in symbols:
            if sym == candidate.get("symbol"):
                conf = candidate.get("meta_probability") or candidate.get("confidence") or 0.55
                expected_rets.append(conf - 0.5)
            else:
                expected_rets.append(0.05)  # existing positions: mild positive prior

        caps = [max(10.0, t.get("usdt_value", 0)) for t in open_trades] + [max(10.0, size_usdt)]
        budget = max(portfolio.get("balance", 0), size_usdt)

        result = self.solve(symbols, expected_rets, caps, budget,
                            max_single_pct=0.25)
        if not result.get("solved"):
            self.last_solve = {"solved": False, "reason": result.get("reason"),
                               "symbols": symbols}
            return {"adjusted_usdt": size_usdt, "joint": False, "reason": result.get("reason")}

        idx = symbols.index(candidate.get("symbol"))
        adjusted = float(result["notional_usdt"][idx])
        # Never let joint sizing inflate a size the per-signal caps rejected;
        # joint is a de-correlation adjuster, not a cap-raiser.
        adjusted = min(adjusted, size_usdt)
        self.last_solve = {
            "solved": True,
            "symbols": symbols,
            "weights": result["weights"],
            "notional_usdt": result["notional_usdt"],
            "portfolio_risk": result["portfolio_risk"],
            "expected_return": result["expected_return"],
            "candidate": candidate.get("symbol"),
            "adjusted_usdt": round(adjusted, 2),
            "raw_size_usdt": round(size_usdt, 2),
        }
        return {
            "adjusted_usdt": round(adjusted, 2),
            "joint": True,
            "symbols": symbols,
            "weights": result["weights"],
            "notional": result["notional_usdt"],
            "portfolio_risk": result["portfolio_risk"],
            "expected_return": result["expected_return"],
        }
