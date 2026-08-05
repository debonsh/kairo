"""Backtest Report — generates professional tear sheets using quantstats."""

from pathlib import Path
from datetime import datetime
from loguru import logger

import pandas as pd
import numpy as np


def generate_report(store, paper_trader, output_dir: str = "reports") -> str:
    """Generate an HTML tear sheet from trade history.

    Falls back to a basic report if quantstats is unavailable.
    Returns the path to the generated HTML file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    trades = _extract_equity_curve(store, paper_trader)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = output_dir / f"report_{timestamp}.html"

    try:
        import quantstats as qs

        if trades.empty or len(trades) < 2:
            return _generate_fallback(path, trades, "Not enough trade data for full report")

        returns = trades.set_index("date")["return"]
        qs.reports.html(returns, output=str(path), title="Kairo Performance Report")
        logger.info(f"quantstats report written to {path}")
        return str(path)

    except Exception as e:
        logger.warning(f"quantstats report failed: {e} — using fallback")
        return _generate_fallback(path, trades, str(e))


def _extract_equity_curve(store, paper_trader) -> pd.DataFrame:
    """Build daily returns from trade history."""
    try:
        rows = store.conn.execute(
            """SELECT exit_time, pnl, usdt_value, symbol, side, exit_reason
               FROM trades WHERE status='closed' AND pnl IS NOT NULL
               ORDER BY exit_time ASC"""
        ).fetchall()

        if not rows:
            return pd.DataFrame(columns=["date", "return", "equity"])

        records = []
        for r in rows:
            exit_time, pnl, value, symbol, side, reason = r
            date = datetime.fromtimestamp(exit_time / 1000) if exit_time else datetime.now()
            records.append({
                "date": date,
                "pnl": pnl or 0,
                "value": value or 0,
                "symbol": symbol or "?",
                "side": side or "?",
                "reason": reason or "?",
            })

        df = pd.DataFrame(records)
        df = df.sort_values("date")

        initial_equity = 5000.0
        df["equity"] = initial_equity + df["pnl"].cumsum()
        prev = df["equity"].shift(1).fillna(initial_equity)
        df["return"] = (df["equity"] - prev) / prev

        return df

    except Exception as e:
        logger.warning(f"Equity curve extraction failed: {e}")
        return pd.DataFrame(columns=["date", "return", "equity"])


def _generate_fallback(path: Path, trades: pd.DataFrame, note: str = "") -> str:
    """Generate a simple HTML summary when quantstats is unavailable."""
    total_pnl = float(trades["pnl"].sum()) if not trades.empty and "pnl" in trades else 0
    num_trades = len(trades)
    wins = int((trades["pnl"] > 0).sum()) if not trades.empty and "pnl" in trades else 0
    losses = num_trades - wins
    win_rate = (wins / num_trades * 100) if num_trades > 0 else 0

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Kairo Report</title>
<style>
body{{background:#0a0a0f;color:#cdd6f4;font:14px/1.5 monospace;padding:32px 40px}}
h1{{color:#00ff88;font-size:22px;font-weight:400}}
.metric{{display:flex;gap:16px;margin:16px 0}}
.box{{background:#12121a;border:1px solid #1e1e2e;padding:12px 16px;min-width:140px}}
.box .label{{color:#6c7086;font-size:11px}}
.box .value{{color:#cdd6f4;font-size:20px;margin-top:4px}}
.box .green{{color:#00ff88}}
.box .red{{color:#ff4466}}
.note{{color:#ffaa00;font-size:12px;margin-top:16px}}
</style></head><body>
<h1>Kairo Performance Report</h1>
<div class="metric">
<div class="box"><div class="label">Total PnL</div><div class="value {'green' if total_pnl >= 0 else 'red'}">${total_pnl:.2f}</div></div>
<div class="box"><div class="label">Total Trades</div><div class="value">{num_trades}</div></div>
<div class="box"><div class="label">Win Rate</div><div class="value {'green' if win_rate >= 50 else 'red'}">{win_rate:.1f}%</div></div>
<div class="box"><div class="label">W/L</div><div class="value">{wins}/{losses}</div></div>
</div>
{f'<div class="note">{note}</div>' if note else ''}
</body></html>"""

    path.write_text(html)
    logger.info(f"Fallback report written to {path}")
    return str(path)


def get_summary_metrics(store, paper_trader) -> dict:
    """Return key performance metrics as a dict for API consumption."""
    trades_df = _extract_equity_curve(store, paper_trader)
    if trades_df.empty or "pnl" not in trades_df or len(trades_df) < 2:
        return {"error": "Not enough data"}

    pnls = trades_df["pnl"].values
    total_pnl = float(pnls.sum())
    wins = int((pnls > 0).sum())
    losses = int((pnls <= 0).sum())
    win_rate = wins / max(len(pnls), 1) * 100

    avg_win = float(pnls[pnls > 0].mean()) if wins > 0 else 0
    avg_loss = float(pnls[pnls <= 0].mean()) if losses > 0 else 0
    best = float(pnls.max())
    worst = float(pnls.min())

    equity = trades_df["equity"].values
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    max_dd = float(drawdown.min()) * 100 if len(drawdown) > 0 else 0

    returns = trades_df["return"].dropna().values
    sharpe = float(np.mean(returns) / np.std(returns) * np.sqrt(365)) if len(returns) > 1 and np.std(returns) > 0 else 0
    sortino = float(np.mean(returns) / np.std(returns[returns < 0]) * np.sqrt(365)) if len(returns[returns < 0]) > 0 and np.std(returns[returns < 0]) > 0 else 0

    return {
        "total_pnl": round(total_pnl, 2),
        "total_trades": len(pnls),
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 1),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "best_trade": round(best, 2),
        "worst_trade": round(worst, 2),
        "max_drawdown_pct": round(max_dd, 1),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "profit_factor": round(abs(avg_win * wins / (abs(avg_loss) * losses)), 2) if (losses > 0 and abs(avg_loss) > 0) else None,
    }
