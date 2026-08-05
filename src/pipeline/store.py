"""DuckDB storage operations for market data."""

import threading
import duckdb
from pathlib import Path
from loguru import logger
from .schema import SCHEMA, INDEXES


class MarketStore:
    """DuckDB storage with ONE connection PER THREAD.

    DuckDB connections are not thread-safe: sharing a single connection
    across threads (trading-loop writes + API reads + WS pushes) is
    undefined behavior — it produced garbled rows and a transient
    ``IndexError`` in ``/candles`` right after startup. Every thread gets
    its own connection to the same database file (DuckDB multiplexes
    connections to one path within a process onto a single database
    instance and serializes at that level), so a read can never interleave
    with a write on the same connection.
    """

    def __init__(self, db_path: str = "data/market.db"):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path)
        self._local = threading.local()
        self._conns: list = []
        self._conns_lock = threading.Lock()
        self._closed = False
        self.conn  # create the constructing thread's connection up front
        self._init_tables()

    @property
    def conn(self):
        """The calling thread's own connection (created lazily).

        Connection count is bounded by the number of distinct threads that
        touch the store (the uvicorn worker pool caps it at ~40), all sharing
        one DuckDB database instance. Connections are released in ``close()``
        — shutdown-only: daemon threads (API/WS) may still hold stale
        connections afterward, which is harmless while the process exits.
        """
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = duckdb.connect(self.db_path)
            self._local.conn = conn
            with self._conns_lock:
                if not self._closed:
                    self._conns.append(conn)
        return conn

    def _init_tables(self):
        self.conn.execute(SCHEMA)
        self.conn.execute(INDEXES)
        logger.info("DuckDB tables initialized")

    def insert_candles(self, exchange: str, symbol: str, timeframe: str, candles: list) -> int:
        rows = [
            {
                "exchange": exchange,
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": int(c[0]),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
                "trades": len(c) > 6 and c[6] or 0,
            }
            for c in candles
        ]
        existing = self.conn.execute(
            "SELECT timestamp FROM candles WHERE exchange=? AND symbol=? AND timeframe=?",
            [exchange, symbol, timeframe],
        ).fetchall()
        existing_ts = {r[0] for r in existing}
        new_rows = [r for r in rows if r["timestamp"] not in existing_ts]
        if not new_rows:
            return 0

        self.conn.executemany(
            """INSERT OR REPLACE INTO candles
               VALUES ($exchange, $symbol, $timeframe, $timestamp, $open, $high, $low, $close, $volume, $trades)""",
            new_rows,
        )
        logger.debug(f"Inserted {len(new_rows)} candles for {exchange}:{symbol}:{timeframe}")
        return len(new_rows)

    def get_candles(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        query = "SELECT * FROM candles WHERE exchange=? AND symbol=? AND timeframe=?"
        params = [exchange, symbol, timeframe]
        if start_ms:
            query += " AND timestamp >= ?"
            params.append(start_ms)
        if end_ms:
            query += " AND timestamp <= ?"
            params.append(end_ms)
        query += " ORDER BY timestamp ASC"
        if limit:
            query += f" LIMIT {limit}"

        result = self.conn.execute(query, params).fetchdf()
        return result.to_dict("records")

    def get_latest_candle(self, exchange: str, symbol: str, timeframe: str) -> dict | None:
        result = self.conn.execute(
            """SELECT * FROM candles
               WHERE exchange=? AND symbol=? AND timeframe=?
               ORDER BY timestamp DESC LIMIT 1""",
            [exchange, symbol, timeframe],
        ).fetchone()
        if result:
            return {
                "exchange": result[0], "symbol": result[1], "timeframe": result[2],
                "timestamp": result[3], "open": result[4], "high": result[5],
                "low": result[6], "close": result[7], "volume": result[8], "trades": result[9],
            }
        return None

    def insert_ticker(self, exchange: str, ticker_data: dict):
        self.conn.execute(
            """INSERT OR REPLACE INTO tickers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                exchange,
                ticker_data["symbol"],
                ticker_data["timestamp"],
                ticker_data.get("bid"),
                ticker_data.get("ask"),
                ticker_data.get("last"),
                ticker_data.get("baseVolume") or ticker_data.get("volume_24h"),
                ticker_data.get("percentage") or ticker_data.get("change_24h"),
                ticker_data.get("high"),
                ticker_data.get("low"),
            ],
        )

    def insert_info_bars(self, exchange: str, symbol: str, bar_type: str, bars: list) -> int:
        """Persist information-driven bars (volume/dollar/tick) from the live
        WebSocket stream. Each bar dict has the shape emitted by
        ``InformationBars._flush()`` (timestamp/open/high/low/close/volumes/trades)."""
        if not bars:
            return 0
        rows = []
        for b in bars:
            ts = int(b.get("timestamp", 0))
            if not ts:
                continue
            rows.append({
                "exchange": exchange, "symbol": symbol, "bar_type": bar_type,
                "timestamp": ts, "open": float(b.get("open", 0)),
                "high": float(b.get("high", 0)), "low": float(b.get("low", 0)),
                "close": float(b.get("close", 0)),
                "base_volume": float(b.get("base_volume", 0)),
                "quote_volume": float(b.get("quote_volume", 0)),
                "trades": int(b.get("trades", 0)),
            })
        if not rows:
            return 0
        existing = self.conn.execute(
            "SELECT timestamp FROM info_bars WHERE exchange=? AND symbol=? AND bar_type=?",
            [exchange, symbol, bar_type],
        ).fetchall()
        existing_ts = {r[0] for r in existing}
        new_rows = [r for r in rows if r["timestamp"] not in existing_ts]
        if not new_rows:
            return 0
        self.conn.executemany(
            """INSERT OR REPLACE INTO info_bars
               VALUES ($exchange, $symbol, $bar_type, $timestamp, $open, $high,
                       $low, $close, $base_volume, $quote_volume, $trades)""",
            new_rows,
        )
        return len(new_rows)

    def log_trade(self, trade: dict) -> str:
        import uuid
        trade_id = str(uuid.uuid4())
        self.conn.execute(
            """INSERT INTO trades (id, exchange, symbol, side, entry_price, quantity, usdt_value,
               entry_time, status, stop_loss, take_profit, strategy)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)""",
            [trade_id, trade["exchange"], trade["symbol"], trade["side"],
             trade["entry_price"], trade["quantity"], trade["usdt_value"],
             trade["entry_time"], trade["stop_loss"], trade["take_profit"],
             trade.get("strategy")],
        )
        return trade_id

    def update_trade_exit(
        self,
        trade_id: str,
        exit_price: float,
        exit_time: int,
        reason: str,
        pnl: float | None = None,
        pnl_pct: float | None = None,
    ):
        """Mark a trade closed and persist its realized PnL.

        pnl/pnl_pct were historically never written to the DB, which broke every
        DB consumer that filters on `pnl IS NOT NULL` (TaxCalculator, FuturesGate,
        report, memory, finetune). They are now stored alongside the exit.
        """
        self.conn.execute(
            "UPDATE trades SET exit_price=?, exit_time=?, exit_reason=?, status='closed', "
            "pnl=?, pnl_pct=? WHERE id=?",
            [exit_price, exit_time, reason, pnl, pnl_pct, trade_id],
        )

    def log_agent_decision(self, decision_id: str, symbol: str, agent: str, decision: dict, snapshot: dict | None = None, latency_ms: int = 0):
        import json
        import uuid as uuidlib
        try:
            uid = uuidlib.UUID(decision_id)
        except ValueError:
            uid = uuidlib.uuid4()
        self.conn.execute(
            "INSERT INTO agent_decisions VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)",
            [str(uid), symbol, agent, json.dumps(decision), json.dumps(snapshot) if snapshot else None, latency_ms],
        )

    def insert_portfolio_snapshot(self, balance: float, equity: float,
                                   open_positions: int, daily_pnl: float = 0.0,
                                   total_pnl: float = 0.0, drawdown_pct: float = 0.0):
        """Persist one portfolio point — the real equity-history source for the
        dashboard (the in-memory equity curve only reflects the last 20 trades)."""
        try:
            self.conn.execute(
                """INSERT OR REPLACE INTO portfolio_snapshots
                   VALUES (CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)""",
                [float(balance), float(equity), int(open_positions),
                 float(daily_pnl), float(total_pnl), float(drawdown_pct)],
            )
        except Exception as e:
            logger.debug(f"Portfolio snapshot skip: {e}")

    def get_portfolio_history(self, limit: int = 500) -> list[dict]:
        """Recent portfolio_snapshots, oldest first — for the real equity curve."""
        try:
            rows = self.conn.execute(
                """SELECT timestamp, balance, equity, open_positions, daily_pnl,
                          total_pnl, drawdown_pct
                   FROM portfolio_snapshots ORDER BY timestamp ASC LIMIT """ + str(int(limit)),
            ).fetchall()
            return [{
                "t": r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0]),
                "balance": round(float(r[1]), 2),
                "equity": round(float(r[2]), 2),
                "open_positions": int(r[3]),
                "daily_pnl": round(float(r[4] or 0), 2),
                "total_pnl": round(float(r[5] or 0), 2),
                "drawdown_pct": round(float(r[6] or 0), 2),
            } for r in rows]
        except Exception as e:
            logger.debug(f"Portfolio history read skip: {e}")
            return []

    def get_open_positions(self) -> list[dict]:
        return self.conn.execute(
            "SELECT * FROM trades WHERE status='open' ORDER BY entry_time DESC"
        ).fetchdf().to_dict("records")

    def close(self):
        """Close every connection this store created (any thread).

        Shutdown-only: after this, no new connections are handed out, and
        daemon threads holding stale connections will see
        ``InvalidInputException: Connection closed`` on later use (fine while
        the process is exiting). Idempotent.
        """
        with self._conns_lock:
            conns, self._conns = self._conns, []
            self._closed = True
        for conn in conns:
            try:
                conn.close()
            except Exception:
                pass
