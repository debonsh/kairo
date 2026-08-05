"""Kairo API — clean JSON REST interface. No Swagger, no slop."""

import asyncio
import threading

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path


class ControlRequest(BaseModel):
    command: str  # stop | pause | resume


# Dashboard push state — the trading loop bumps this version counter whenever
# something worth showing changes (new trade, position closed, cycle done).
# Each connected WebSocket client re-sends a fresh payload when it sees the
# counter move. Safe to call from any thread (trading loop, API handlers).
_ws_lock = threading.Lock()
_ws_version = 0


def invalidate_dashboard() -> None:
    """Signal WebSocket clients that a fresh dashboard payload is available."""
    global _ws_version
    with _ws_lock:
        _ws_version += 1


# Blank canvas for the full UI redesign — the old Kairo Terminal was removed.
# Build the new UI from scratch: drop an index.html in the project root and it
# will be served at / instead of this placeholder.
BLANK_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kairo — UI Redesign</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0f;color:#cdd6f4;font:14px/1.5 'Cascadia Code','JetBrains Mono','Consolas',monospace;min-height:100vh;display:flex;align-items:center;justify-content:center}
.wrap{text-align:center;padding:40px}
.dot{color:#00ff88}
.hint{color:#6c7086;font-size:12px;margin-top:12px}
.hint b{color:#4499ff;font-weight:400}
</style>
</head>
<body>
<div class="wrap">
  <div style="font-size:20px"><span class="dot">◆</span> KAIRO</div>
  <div class="hint">Blank canvas — UI removed. Create <b>index.html</b> in the project root and it will be served here.</div>
</div>
</body>
</html>"""


def create_app(store, paper_trader, orchestrator, killswitch, state=None, futures_trader=None,
               market_maker=None, tri_arb=None, paper_mode: bool = True):
    app = FastAPI(title="Kairo", docs_url=None, redoc_url=None, openapi_url=None)
    # Localhost-only CORS: the dashboard is served from this same origin, so
    # wildcard origins would let ANY webpage the user visits POST to /control
    # and stop the bot (CSRF). Restricting to the local dashboard keeps the
    # browser's same-origin policy on our side. The dev origin (:3000) is
    # allowed so the Next.js terminal can talk to the API during development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:8000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://localhost:3000",
        ],
        allow_methods=["*"], allow_headers=["*"],
    )

    # Local dashboard control must work out of the box: the dashboard calls
    # /control and /mode with user_id 0 (no Telegram auth round-trip). The API
    # binds to 127.0.0.1 only, so authorizing the local user is safe.
    if killswitch is not None:
        try:
            killswitch.add_authorized_user(0)
        except Exception:
            pass

    # Serve the Next.js static export (ui/apps/terminal/out) at /
    # plus its _next/ and fonts/ asset trees. Falls back to the legacy
    # project-root index.html, then the blank canvas.
    TERMINAL_OUT = Path("ui/apps/terminal/out")

    @app.get("/", response_class=HTMLResponse)
    def index():
        """Serve the KAIRO terminal static export at the root."""
        no_cache = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
        terminal = TERMINAL_OUT / "index.html"
        if terminal.exists():
            return HTMLResponse(terminal.read_text(encoding="utf-8"), headers=no_cache)
        canvas = Path("index.html")
        if canvas.exists():
            return HTMLResponse(canvas.read_text(encoding="utf-8"), headers=no_cache)
        return BLANK_HTML

    if TERMINAL_OUT.exists():
        app.mount("/_next", StaticFiles(directory=TERMINAL_OUT / "_next"), name="next-assets")
        app.mount("/fonts", StaticFiles(directory=TERMINAL_OUT / "fonts"), name="fonts")

    @app.get("/status")
    def get_status():
        portfolio = paper_trader.get_portfolio() if paper_trader else {}
        ks = killswitch.get_status() if killswitch else "unknown"
        orch = orchestrator.get_status() if orchestrator else {}
        return {
            "bot": ks,
            "balance": round(portfolio.get("balance", 0), 2),
            "equity": round(portfolio.get("equity", 0), 2),
            "open_positions": portfolio.get("open_positions", 0),
            "total_trades": portfolio.get("total_trades", 0),
            "daily_pnl": round(portfolio.get("daily_pnl", 0), 2),
            "uptime_hours": round(orch.get("uptime_hours", 0), 1),
            "cycles": orch.get("cycles_completed", 0),
            "t": datetime.now().isoformat(),
        }

    @app.get("/positions")
    def get_positions():
        portfolio = paper_trader.get_portfolio() if paper_trader else {}
        open_trades = portfolio.get("open_trades", [])
        return {
            "count": len(open_trades),
            "positions": [
                {
                    "symbol": t.get("symbol", "?"),
                    "side": str(t.get("side", "?")).upper(),
                    "entry": round(t.get("entry_price", 0), 4),
                    "qty": round(t.get("quantity", 0), 6),
                    "value": round(t.get("usdt_value", 0), 2),
                    "sl": round(t.get("stop_loss", 0), 4),
                    "tp": round(t.get("take_profit", 0), 4),
                    "id": str(t.get("id", "")),
                }
                for t in open_trades
            ],
            "t": datetime.now().isoformat(),
        }

    @app.get("/trades")
    def get_trades(limit: int = 20):
        portfolio = paper_trader.get_portfolio() if paper_trader else {}
        recent = list(portfolio.get("recent_trades", []))
        recent.reverse()
        return {
            "count": min(len(recent), limit),
            "trades": [
                {
                    "symbol": t.get("symbol", "?"),
                    "side": str(t.get("side", "?")).upper(),
                    "entry": round(t.get("entry_price", 0), 4),
                    "exit": round(t.get("exit_price", 0), 4) if t.get("exit_price") else None,
                    "pnl": round(t.get("pnl", 0), 2),
                    "pnl_pct": round(t.get("pnl_pct", 0), 2),
                    "reason": t.get("exit_reason", ""),
                    "strategy": t.get("strategy", ""),
                }
                for t in recent[:limit]
            ],
            "t": datetime.now().isoformat(),
        }

    @app.get("/pnl")
    def get_pnl():
        portfolio = paper_trader.get_portfolio() if paper_trader else {}
        trades = portfolio.get("recent_trades", [])
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
        losses = sum(1 for t in trades if t.get("pnl", 0) <= 0)
        return {
            "total_pnl": round(total_pnl, 2),
            "daily_pnl": round(portfolio.get("daily_pnl", 0), 2),
            "total_trades": len(trades),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / len(trades) * 100, 1) if trades else 0,
            "t": datetime.now().isoformat(),
        }

    @app.post("/control")
    def control(request: ControlRequest):
        cmd = request.command.lower()
        if cmd not in ("stop", "pause", "resume"):
            raise HTTPException(400, f"unknown command: {cmd}")
        result = killswitch.handle_command(f"/{cmd}", 0)
        invalidate_dashboard()
        return {"command": cmd, "result": result, "t": datetime.now().isoformat()}

    @app.get("/agents")
    def get_agents():
        orch = orchestrator.get_status() if orchestrator else {}
        return {"orchestrator": orch, "t": datetime.now().isoformat()}

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/candles")
    def get_candles(symbol: str = "BTC/USDT", timeframe: str = "1h", limit: int = 120):
        """Real OHLCV candles from the DuckDB store — always the freshest N
        (queries DESC then reverses, so a long history never drops new bars)."""
        limit = min(max(int(limit), 10), 500)
        rows = []
        try:
            for ex in ("bybit", "binance"):
                fetched = store.conn.execute(
                    "SELECT timestamp, open, high, low, close, volume FROM candles "
                    "WHERE exchange=? AND symbol=? AND timeframe=? "
                    "ORDER BY timestamp DESC LIMIT ?",
                    [ex, symbol, timeframe, limit],
                ).fetchall()
                if fetched:
                    rows = fetched
                    break
        except Exception:
            rows = []
        tail = list(reversed(rows))
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "count": len(tail),
            "candles": [
                {"t": r[0], "o": r[1], "h": r[2], "l": r[3], "c": r[4], "v": r[5]}
                for r in tail
            ],
            "t": datetime.now().isoformat(),
        }

    @app.get("/market")
    def get_market():
        """Return real-time market data from the exchange if available, else cached/demo data."""
        import json
        market_file = Path("data/market_snapshot.json")
        if market_file.exists():
            try:
                return json.loads(market_file.read_text())
            except:
                pass
        # Return demo data as fallback
        return {
            "coins": [
                {"symbol": "BTC/USDT", "price": 66823.45, "change_24h": 2.47},
                {"symbol": "ETH/USDT", "price": 3228.75, "change_24h": 1.32},
                {"symbol": "SOL/USDT", "price": 145.32, "change_24h": 5.71},
                {"symbol": "BNB/USDT", "price": 582.10, "change_24h": 0.93},
            ],
            "total_market_cap": "2.42T",
            "market_cap_change": 3.21,
            "fear_greed_index": 72,
            "fear_greed_label": "GREED",
            "t": datetime.now().isoformat(),
        }

    @app.get("/report")
    def get_report():
        from src.backtest.report import generate_report, get_summary_metrics
        portfolio = paper_trader.get_portfolio() if paper_trader else {}
        trades = portfolio.get("recent_trades", [])
        if len(trades) < 2:
            return {"error": "Not enough trade data — need at least 2 closed trades"}
        metrics = get_summary_metrics(store, paper_trader)
        metrics["t"] = datetime.now().isoformat()
        return metrics

    @app.get("/futures")
    def get_futures():
        gate_result = None
        if state and state.gate:
            gate_result_obj = state.gate.evaluate()
            gate_result = {
                "unlocked": gate_result_obj.unlocked,
                "allowed_leverage": gate_result_obj.allowed_leverage,
                "total_spot_trades": gate_result_obj.total_spot_trades,
                "rolling_sharpe": gate_result_obj.rolling_sharpe,
                "win_rate": gate_result_obj.win_rate,
                "profitable_days": gate_result_obj.profitable_days,
                "checks": gate_result_obj.checks,
                "reason": gate_result_obj.reason,
            }
        ft_status = futures_trader.get_status() if futures_trader else {}
        return {
            "state": state.get_status() if state else {"mode": "vanilla"},
            "gate": gate_result,
            "trader": ft_status,
            "t": datetime.now().isoformat(),
        }

    @app.post("/mode")
    def set_mode(request: ControlRequest):
        cmd = request.command.lower()
        if cmd not in ("vanilla", "aggressive"):
            raise HTTPException(400, f"Unknown mode: {cmd}. Use 'vanilla' or 'aggressive'.")
        if state is None:
            raise HTTPException(400, "State manager not initialized")
        result = state.set_mode(cmd)
        invalidate_dashboard()
        return {"mode": result["mode"], "leverage": result["leverage"],
                "futures_unlocked": result["futures_unlocked"],
                "previous_mode": result["previous_mode"],
                "t": datetime.now().isoformat()}

    @app.get("/report/html")
    def get_report_html():
        from src.backtest.report import generate_report
        path = generate_report(store, paper_trader)
        return {"report_path": path, "t": datetime.now().isoformat()}

    @app.get("/tax")
    def get_tax(year: int | None = None, format: str = "json"):
        from src.monitor.tax_journal import TaxCalculator
        calc = TaxCalculator(store)
        if format == "csv":
            path = calc.export_csv("reports/tax_report.csv", year)
            return {"csv_path": path, "t": datetime.now().isoformat()}
        if format == "schedule":
            return {"schedule": calc.generate_itr_schedule(year), "t": datetime.now().isoformat()}
        return {**calc.compute_tax_liability(year), "t": datetime.now().isoformat()}

    @app.get("/tax/monthly")
    def get_tax_monthly(year: int | None = None):
        from src.monitor.tax_journal import TaxCalculator
        calc = TaxCalculator(store)
        return {"months": calc.get_monthly_summary(year), "t": datetime.now().isoformat()}

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard_html():
        dashboard_path = Path("src/monitor/dashboard.html")
        if dashboard_path.exists():
            return HTMLResponse(dashboard_path.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Dashboard not found</h1>")

    _payload_cache = {"version": -1, "data": None}
    # Serializes the payload rebuild's DuckDB reads (sweep, portfolio history,
    # tri-arb log, correlations) against the trading loop's writes on the same
    # connection. Without this, the WS push loop can collide with insert_candles
    # / log_trade mid-query on the single DuckDB connection.
    _payload_lock = threading.Lock()

    _corr_cache: dict = {"at": 0.0, "data": None}
    _corr_lock = threading.Lock()

    _sweep_cache: dict = {"at": 0.0, "data": None}

    def _control_state() -> dict:
        """Killswitch state for the dashboard control bar."""
        if killswitch is None:
            return {"state": "UNKNOWN", "trading_allowed": True}
        state_name = ("STOPPED" if killswitch.is_stopped
                      else "PAUSED" if killswitch.is_paused else "RUNNING")
        return {
            "state": state_name,
            "trading_allowed": killswitch.trading_allowed(),
            "is_paused": killswitch.is_paused,
            "is_stopped": killswitch.is_stopped,
        }

    def _confidence_sweep_verdict() -> dict:
        """Lightweight re-run of scripts/confidence_sweep.py against the store
        DB, cached 5 minutes. Reports what min_confidence the journal supports."""
        import time as _time
        now = _time.time()
        if _sweep_cache["data"] is not None and (now - _sweep_cache["at"]) < 300:
            return _sweep_cache["data"]

        verdict = {"supported_threshold": None, "n": 0, "recommendation": "NO DATA", "delta_pnl": None}
        try:
            scorecard_rows = []
            pairs = []
            try:
                rows = store.conn.execute(
                    "SELECT predicted_confidence, was_correct FROM scorecard "
                    "WHERE predicted_confidence IS NOT NULL"
                ).fetchall()
                scorecard_rows = [{"confidence": float(r[0]), "was_correct": bool(r[1])} for r in rows]
            except Exception:
                pass
            try:
                decisions = store.conn.execute(
                    "SELECT symbol, timestamp, decision FROM agent_decisions"
                ).fetchall()
                trades = store.conn.execute(
                    "SELECT symbol, entry_time, pnl FROM trades "
                    "WHERE status='closed' AND pnl IS NOT NULL"
                ).fetchall()
                trades_by_sym = {}
                for sym, entry_ms, pnl in trades:
                    trades_by_sym.setdefault(sym, []).append((entry_ms, float(pnl)))
                for sym, ts, decision_json in decisions:
                    if not decision_json:
                        continue
                    try:
                        import json as _json
                        decision = _json.loads(decision_json) if isinstance(decision_json, str) else decision_json
                    except Exception:
                        continue
                    signal = decision.get("signal") or {}
                    confidence = signal.get("confidence")
                    if confidence is None:
                        continue
                    ts_ms = int(ts.timestamp() * 1000) if hasattr(ts, "timestamp") else int(ts)
                    for entry_ms, pnl in trades_by_sym.get(sym, []):
                        if 0 <= entry_ms - ts_ms <= 15 * 60 * 1000:
                            pairs.append({"confidence": float(confidence), "pnl": pnl})
                            break
            except Exception:
                pass

            rows = scorecard_rows if scorecard_rows else pairs
            if rows:
                # Find the threshold (0.50-0.70) with the best avg pnl at >= 30 samples.
                best = None
                current_avg = None
                for t in [round(0.50 + i * 0.01, 2) for i in range(21)]:
                    passed = [r for r in rows if r["confidence"] >= t]
                    if len(passed) < 30:
                        continue
                    pnls = [r.get("pnl") for r in passed]
                    if not any(p is not None for p in pnls):
                        continue
                    avg = sum(p for p in pnls if p is not None) / len(passed)
                    if abs(t - 0.55) < 1e-9:
                        current_avg = avg
                    if best is None or avg > best["avg_pnl"]:
                        best = {"threshold": t, "n": len(passed), "avg_pnl": avg}
                if best:
                    delta = (best["avg_pnl"] - current_avg) if current_avg is not None else best["avg_pnl"]
                    verdict = {
                        "supported_threshold": best["threshold"],
                        "n": best["n"],
                        "avg_pnl": round(best["avg_pnl"], 2),
                        "current": 0.55,
                        "current_avg_pnl": round(current_avg, 2) if current_avg is not None else None,
                        "delta_pnl": round(delta, 2),
                        "recommendation": (f"SUPPORTED {best['threshold']:.2f} @ n={best['n']}"
                                           if best["n"] >= 30 else "NEEDS MORE DATA"),
                    }
                else:
                    verdict = {"supported_threshold": None, "n": len(rows),
                               "recommendation": "NEEDS MORE DATA (<30 matched)"}
            _sweep_cache["at"] = now
            _sweep_cache["data"] = verdict
        except Exception:
            _sweep_cache["at"] = now
            _sweep_cache["data"] = verdict
        return verdict

    def _compute_correlations() -> dict:
        """Real pairwise correlation network from stored 4h candle closes.

        Computed once per 2 minutes (TTL cache). The lock serializes access
        to the shared DuckDB connection (WS push loop + REST handlers + the
        trading loop all use store.conn), so concurrent queries never race.
        """
        import time as _time
        import numpy as np

        now = _time.time()
        with _corr_lock:
            if _corr_cache["data"] is not None and (now - _corr_cache["at"]) < 120:
                return _corr_cache["data"]
            return _compute_correlations_locked(now)

    def _compute_correlations_locked(now: float) -> dict:
        nodes: list[dict] = []
        links: list[dict] = []
        try:
            syms = [
                r[0] for r in store.conn.execute(
                    "SELECT DISTINCT symbol FROM candles "
                    "WHERE symbol LIKE '%/USDT' ORDER BY symbol LIMIT 10"
                ).fetchall()
            ]
            series: dict[str, list[float]] = {}
            for s in syms:
                rows = store.get_candles("bybit", s, "4h", limit=500) or \
                       store.get_candles("binance", s, "4h", limit=500) or []
                closes = [float(r["close"]) for r in rows][-60:]
                if len(closes) >= 20:
                    series[s] = closes

            base = "BTC/USDT" if "BTC/USDT" in series else (syms[0] if syms else None)
            if base:
                btc = np.array(series[base][-40:], dtype=float)
                for s in series:
                    if s == base:
                        continue
                    arr = np.array(series[s][-40:], dtype=float)
                    n = min(len(btc), len(arr))
                    if n < 20:
                        continue
                    b, a = btc[-n:], arr[-n:]
                    corr = 0.0
                    if np.std(a) > 0 and np.std(b) > 0:
                        corr = float(np.corrcoef(a, b)[0, 1])
                    if abs(corr) >= 0.3:
                        links.append({"a": base, "b": s, "corr": round(corr, 3)})

            for s, closes in series.items():
                chg = (closes[-1] / closes[-7] - 1) * 100 if len(closes) >= 7 and closes[-7] > 0 else 0.0
                nodes.append({"id": s, "chg": round(chg, 2)})

            _corr_cache["at"] = now
            _corr_cache["data"] = {"nodes": nodes, "links": links}
        except Exception:
            _corr_cache["at"] = now
            _corr_cache["data"] = {"nodes": nodes, "links": links}
        return _corr_cache["data"]

    def _dashboard_payload():
        # Shared cache keyed by version counter — N open tabs share ONE build
        # (a fresh FuturesGate.evaluate() per client would be wasteful).
        if _payload_cache["version"] == _ws_version and _payload_cache["data"] is not None:
            return _payload_cache["data"]
        with _payload_lock:
            # Double-check under the lock: another thread may have built it.
            if _payload_cache["version"] == _ws_version and _payload_cache["data"] is not None:
                return _payload_cache["data"]
            return _dashboard_payload_locked()

    def _dashboard_payload_locked():
        portfolio = paper_trader.get_portfolio() if paper_trader else {}
        ks = killswitch.get_status() if killswitch else "unknown"
        orch = orchestrator.get_status() if orchestrator else {}

        trades = portfolio.get("recent_trades", [])
        closed = [t for t in trades if t.get("pnl") is not None]
        pnl_series = [t.get("pnl", 0) for t in closed]

        balance = round(portfolio.get("balance", 0), 2)
        daily_pnl = round(portfolio.get("daily_pnl", 0), 2)
        total_pnl = round(sum(pnl_series), 2)
        wins = sum(1 for p in pnl_series if p > 0)
        losses = sum(1 for p in pnl_series if p <= 0)
        win_rate = round(wins / max(len(pnl_series), 1) * 100, 1)

        equity = balance
        equity_curve = []
        cumulative = 0
        trades_overlay = []
        for i, pnl in enumerate(pnl_series):
            cumulative += pnl
            equity_curve.append(round(5000 + cumulative, 2))
            t = closed[i]
            trades_overlay.append({
                "x": i,
                "y": round(5000 + cumulative, 2),
                "pnl": round(pnl, 2),
                "side": str(t.get("side", "?")).upper(),
                "symbol": t.get("symbol", "?"),
                "reason": t.get("exit_reason", ""),
            })

        signal_confidence = []
        signal_outcome = []
        for t in closed:
            conf = t.get("confidence", 0) if isinstance(t.get("confidence"), (int, float)) else 0.5
            signal_confidence.append(conf)
            signal_outcome.append(1 if t.get("pnl", 0) > 0 else 0)

        # REAL per-strategy stats from the trade journal
        strat_agg: dict[str, dict] = {}
        for t in closed:
            name = (t.get("strategy") or "AGENT").upper()
            s = strat_agg.setdefault(name, {"trades": 0, "wins": 0, "pnl": 0.0, "pcts": []})
            pnl = t.get("pnl", 0) or 0
            s["trades"] += 1
            s["pnl"] += pnl
            if pnl > 0:
                s["wins"] += 1
            pct = t.get("pnl_pct")
            if isinstance(pct, (int, float)):
                s["pcts"].append(pct)
        strategies = [
            {
                "name": k,
                "trades": v["trades"],
                "win_rate": round(v["wins"] / v["trades"] * 100, 1),
                "pnl": round(v["pnl"], 2),
                "avg_pnl_pct": round(sum(v["pcts"]) / len(v["pcts"]), 2) if v["pcts"] else 0.0,
            }
            for k, v in sorted(strat_agg.items(), key=lambda x: -x[1]["pnl"])
        ]

        # REAL live trade feed (most recent first)
        live_feed = [
            {
                "symbol": t.get("symbol", "?"),
                "side": str(t.get("side", "?")).upper(),
                "pnl": round(t.get("pnl", 0), 2),
                "pnl_pct": round(t.get("pnl_pct", 0), 2),
                "reason": t.get("exit_reason", ""),
                "strategy": (t.get("strategy") or "AGENT").upper(),
                "entry": round(t.get("entry_price", 0), 4),
                "exit": round(t.get("exit_price", 0), 4) if t.get("exit_price") else None,
                "time": (t.get("exit_time") or t.get("entry_time") or 0) // 1000,
            }
            for t in reversed(closed[-30:])
        ]

        # REAL market correlation network from candle history
        # Note: strategies/live_feed reflect the last 20 closed trades (the
        # in-memory paper-trader window), not the full journal.
        correlations = _compute_correlations()

        # Live position PnL: mark-to-market against the latest ticker price.
        import json as _json
        _live_prices = {}
        try:
            _snap = Path("data/market_snapshot.json")
            if _snap.exists():
                _live_prices = {
                    c.get("symbol"): float(c.get("price", 0))
                    for c in _json.loads(_snap.read_text(encoding="utf-8")).get("coins", [])
                    if c.get("symbol") and c.get("price")
                }
        except Exception:
            pass

        def _mark_pnl(t: dict) -> dict:
            px = _live_prices.get(t.get("symbol", ""))
            entry = float(t.get("entry_price", 0) or 0)
            qty = float(t.get("quantity", 0) or 0)
            side = str(t.get("side", "long")).lower()
            upnl = 0.0
            if px and entry > 0 and qty:
                raw = (px - entry) * qty
                if side in ("short", "sell"):
                    raw = -raw
                upnl = round(raw, 2)
            return {
                "symbol": t.get("symbol", "?"),
                "side": str(t.get("side", "?")).upper(),
                "entry": round(entry, 4),
                "qty": round(qty, 6),
                "value": round(t.get("usdt_value", 0), 2),
                "price": px or round(entry, 4),
                "upnl": upnl,
                "upnl_pct": round(upnl / (entry * qty) * 100, 2) if entry * qty > 0 else 0.0,
                "sl": round(t.get("stop_loss", 0), 4),
                "tp": round(t.get("take_profit", 0), 4),
            }

        mm_status = None
        if market_maker is not None:
            try:
                mm_status = market_maker.status()
            except Exception:
                mm_status = None

        tri_status = None
        if tri_arb is not None:
            try:
                tri_status = tri_arb.get_status()
            except Exception:
                tri_status = None

        try:
            tri_recent = store.conn.execute(
                "SELECT loop, spread_pct, estimated_profit, executed, timestamp "
                "FROM tri_arb_opportunities ORDER BY timestamp DESC LIMIT 5"
            ).fetchall()
            tri_recent = [
                {"loop": r[0], "spread_pct": round(float(r[1] or 0), 4),
                 "est_profit": round(float(r[2] or 0), 4),
                 "executed": bool(r[3]), "ts": int(r[4] or 0)}
                for r in tri_recent
            ]
        except Exception:
            tri_recent = []

        payload = {
            "summary": {
                "bot": ks,
                "balance": balance,
                "equity": equity,
                "daily_pnl": daily_pnl,
                "total_pnl": total_pnl,
                "open_positions": portfolio.get("open_positions", 0),
                "total_trades": len(closed),
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "uptime_hours": round(orch.get("uptime_hours", 0), 1),
                "cycles": orch.get("cycles_completed", 0),
                "paper_mode": paper_mode,
                "llm": orch.get("llm"),
                "control": _control_state(),
            },
            "equity_curve": equity_curve,
            "equity_history": store.get_portfolio_history(limit=500),
            "trades_overlay": trades_overlay,
            "signal_confidence": signal_confidence,
            "signal_outcome": signal_outcome,
            "positions": [_mark_pnl(t) for t in portfolio.get("open_trades", [])],
            "recent_trades": [
                {
                    "symbol": t.get("symbol", "?"),
                    "side": str(t.get("side", "?")).upper(),
                    "pnl": round(t.get("pnl", 0), 2),
                    "pnl_pct": round(t.get("pnl_pct", 0), 2),
                    "reason": t.get("exit_reason", ""),
                    "strategy": t.get("strategy", ""),
                }
                for t in closed[-10:]
            ],
            "strategies": strategies,
            "live_feed": live_feed,
            "correlations": correlations,
            "futures": _futures_snapshot(state, store),
            "market_maker": mm_status,
            "tri_arb": ({"status": tri_status, "recent": tri_recent}
                        if tri_status is not None else None),
            "joint_sizer": orch.get("joint_sizer") or {},
            "confidence_sweep": _confidence_sweep_verdict(),
            "t": datetime.now().isoformat(),
        }
        _payload_cache["version"] = _ws_version
        _payload_cache["data"] = payload
        return payload

    @app.get("/dashboard-data")
    def dashboard_data():
        return _dashboard_payload()

    @app.websocket("/ws")
    async def ws_dashboard(websocket: WebSocket):
        """Live dashboard push channel.

        Sends the full dashboard payload immediately on connect, then re-sends
        whenever the trading loop bumps the version counter (new trade, closed
        position, finished cycle). Runs on the uvicorn event loop only — all
        cross-thread signalling happens through the shared version counter.
        """
        await websocket.accept()
        last_sent = -1
        try:
            await websocket.send_json(_dashboard_payload())
            last_sent = _ws_version
            while True:
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
                if _ws_version != last_sent:
                    last_sent = _ws_version
                    try:
                        await websocket.send_json(_dashboard_payload())
                    except Exception:
                        break
        except Exception:
            pass  # client disconnected — drop silently

    def _futures_snapshot(state, store):
        try:
            from src.execution.futures_gate import FuturesGate
            gate = FuturesGate(store, mode=state.get_mode() if state else "vanilla")
            r = gate.evaluate()
            return {
                "mode": state.get_mode() if state else "vanilla",
                "leverage": state.leverage if state else 1.0,
                "futures_unlocked": r.unlocked,
                "allowed_leverage": r.allowed_leverage,
                "checks": r.checks,
                "total_spot_trades": r.total_spot_trades,
                "rolling_sharpe": r.rolling_sharpe,
                "win_rate": r.win_rate,
                "profitable_days": r.profitable_days,
                "reason": r.reason,
                "execution_path": "futures" if (state and state.should_use_futures()) else "spot",
            }
        except Exception:
            return None

    return app
