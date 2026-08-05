"""DuckDB schema definitions for market data storage."""

SCHEMA = """
-- OHLCV candles table
CREATE TABLE IF NOT EXISTS candles (
    exchange VARCHAR,
    symbol VARCHAR,
    timeframe VARCHAR,
    timestamp BIGINT,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    trades INTEGER,
    PRIMARY KEY (exchange, symbol, timeframe, timestamp)
);

-- Real-time ticker snapshots
CREATE TABLE IF NOT EXISTS tickers (
    exchange VARCHAR,
    symbol VARCHAR,
    timestamp BIGINT,
    bid DOUBLE,
    ask DOUBLE,
    last DOUBLE,
    volume_24h DOUBLE,
    change_24h DOUBLE,
    high_24h DOUBLE,
    low_24h DOUBLE,
    PRIMARY KEY (exchange, symbol, timestamp)
);

-- Trade journal
CREATE TABLE IF NOT EXISTS trades (
    id VARCHAR PRIMARY KEY,
    exchange VARCHAR,
    symbol VARCHAR,
    side VARCHAR NOT NULL,
    entry_price DOUBLE NOT NULL,
    exit_price DOUBLE,
    quantity DOUBLE NOT NULL,
    usdt_value DOUBLE NOT NULL,
    entry_time BIGINT NOT NULL,
    exit_time BIGINT,
    pnl DOUBLE,
    pnl_pct DOUBLE,
    status VARCHAR DEFAULT 'open',
    stop_loss DOUBLE,
    take_profit DOUBLE,
    strategy VARCHAR,
    agent_decision JSON,
    exit_reason VARCHAR
);

-- Agent decision log
CREATE TABLE IF NOT EXISTS agent_decisions (
    id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    symbol VARCHAR,
    agent VARCHAR NOT NULL,
    decision JSON NOT NULL,
    market_snapshot JSON,
    latency_ms INTEGER
);

-- Learning scorecard
CREATE TABLE IF NOT EXISTS scorecard (
    id VARCHAR PRIMARY KEY,
    trade_id VARCHAR REFERENCES trades(id),
    predicted_direction VARCHAR,
    actual_direction VARCHAR,
    predicted_confidence DOUBLE,
    was_correct BOOLEAN,
    agent VARCHAR,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Portfolio snapshots
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    timestamp TIMESTAMP,
    balance DOUBLE,
    equity DOUBLE,
    open_positions INTEGER,
    daily_pnl DOUBLE,
    total_pnl DOUBLE,
    drawdown_pct DOUBLE,
    PRIMARY KEY (timestamp)
);

-- Fear & Greed index
CREATE TABLE IF NOT EXISTS fear_greed (
    timestamp TIMESTAMP PRIMARY KEY,
    value INTEGER,
    classification VARCHAR
);

-- Social sentiment mentions
CREATE TABLE IF NOT EXISTS social_mentions (
    symbol VARCHAR,
    timestamp BIGINT,
    source VARCHAR,
    mentions INTEGER,
    sentiment_score DOUBLE,
    sentiment_label VARCHAR,
    headline_count INTEGER,
    trending_score DOUBLE,
    PRIMARY KEY (symbol, timestamp, source)
);

-- Arbitrage opportunity log
CREATE TABLE IF NOT EXISTS arb_opportunities (
    timestamp BIGINT,
    symbol VARCHAR,
    buy_exchange VARCHAR,
    sell_exchange VARCHAR,
    buy_price DOUBLE,
    sell_price DOUBLE,
    spread_pct DOUBLE,
    estimated_profit DOUBLE,
    profitable BOOLEAN,
    PRIMARY KEY (timestamp, symbol)
);

-- Information-driven bars from the live stream (volume/dollar/tick/CUSUM)
CREATE TABLE IF NOT EXISTS info_bars (
    exchange VARCHAR,
    symbol VARCHAR,
    bar_type VARCHAR,
    timestamp BIGINT,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    base_volume DOUBLE,
    quote_volume DOUBLE,
    trades INTEGER,
    PRIMARY KEY (exchange, symbol, bar_type, timestamp)
);

-- Market maker fills (inventory, quotes, pnl per cycle)
CREATE TABLE IF NOT EXISTS market_making (
    timestamp BIGINT,
    symbol VARCHAR,
    side VARCHAR,
    price DOUBLE,
    quantity DOUBLE,
    fee DOUBLE,
    inventory DOUBLE,
    inventory_value DOUBLE,
    realized_pnl DOUBLE,
    PRIMARY KEY (timestamp, symbol, side)
);

-- Triangular arbitrage opportunities (single-exchange 3-leg loops)
CREATE TABLE IF NOT EXISTS tri_arb_opportunities (
    timestamp BIGINT,
    loop VARCHAR,
    leg1 VARCHAR,
    leg2 VARCHAR,
    leg3 VARCHAR,
    implied_price DOUBLE,
    actual_price DOUBLE,
    spread_pct DOUBLE,
    estimated_profit DOUBLE,
    executed BOOLEAN,
    PRIMARY KEY (timestamp, loop)
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_candles_symbol_ts ON candles(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_candles_exchange_sym ON candles(exchange, symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_entry ON trades(entry_time);
CREATE INDEX IF NOT EXISTS idx_agent_ts ON agent_decisions(timestamp);
CREATE INDEX IF NOT EXISTS idx_scorecard_trade ON scorecard(trade_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_ts ON portfolio_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_social_sym_ts ON social_mentions(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_arb_ts ON arb_opportunities(timestamp);
"""
