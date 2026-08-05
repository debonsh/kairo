# Changelog

## v1.1 — Roadmap Implementation (2026-08-04)

### Priority 0 — Finish What Was Built ✅
- **48h time-stop enforced**: `position.max_hold_time_hours` (48h) now closes stale positions (`time_stop` exit reason). Previously configured but unenforced — a choppy-market position could sit open forever, occupying one of the 5 slots. Live profile params read per tick via state manager.
- **Info bars wired live**: `info_bars.py` folded into the live stream — `LiveStream` converts incoming 15m OHLCV into info bars (`info_bars` DuckDB table, `store.insert_info_bars()`), and `_build_market_data` drives the 15m signal block from volume bars (config: `trading.info_bars.enabled/bar_type`). Live signal generation no longer runs purely on wall-clock OHLCV.
- **min_confidence sweep tool**: `scripts/confidence_sweep.py` sweeps 0.50–0.70 against the journal (scorecard + decision→trade joins) and reports the data-supported threshold with sample-size caveats.
- **Meta-labeler sample-size caveats**: `MetaLabelClassifier` tracks `training_samples` + `trusted` flag (min 100); `MetaLabelRetrainer` returns `trusted`/`caveat`; every prediction carries the sample size so low-trust RF output is treated as advisory (same discipline as FuturesGate).

### Priority 1 — New Strategy Families ✅
- **Market Making execution path**: `src/execution/market_maker.py` — quotes both sides of the book, inventory-skew risk rules (max inventory, skew ratio, quote-ratio), paper fill simulation, `market_making` DuckDB log. Separate path + own gate conditions (not a 6th `evaluate()`). Opt-in via `market_making.enabled`; risk rules in risk_rules.yaml.
- **Triangular Arbitrage**: `src/execution/triangular_arb.py` — single-exchange 3-leg loops (USDT→A→B→USDT), fee-clearing detection, paper execution, `tri_arb_opportunities` log. Opt-in via `triangular_arb.enabled`.
- **Alpha discovery**: `src/backtest/alpha_search.py` — formulaic alpha candidate generator (primitive grammar + direction), scores on historical candles, ranks by mean Sharpe, writes `data/alpha_candidates.json` for the existing validation pipeline.

### Priority 2 — Portfolio & Execution ✅
- **Joint position sizing (cvxpy)**: `src/agents/joint_sizer.py` — convex optimizer sizes positions jointly against open positions' return correlation (aligned 15m candles), respecting per-position Kelly/vol caps; wired into the orchestrator after risk sizing, before the gate. Falls back to per-signal sizing when cvxpy/correlation unavailable.
- **Fill validation for SpreadOptimizer**: `src/backtest/fill_validation.py` — queue-position + latency-aware limit fill simulation vs stored candles; validates the optimizer's learned fill-rate assumptions.

### Priority 3 — Research Velocity ✅
- **vectorbt parameter search**: `scripts/vectorbt_search.py` — numba-accelerated vectorized SMA/RSI sweeps for the search phase; confirms with the event-driven BacktestEngine before shadow mode.

### New DB Tables
`info_bars`, `market_making`, `tri_arb_opportunities`

### New/Updated Scripts
`scripts/confidence_sweep.py`, `scripts/vectorbt_search.py`, `src/backtest/alpha_search.py`, `src/backtest/fill_validation.py`

---

## v1.0 — Production (2026-08-04)

### v0.1.0 — Foundation ✅
- Data pipeline: ccxt historical + WebSocket + DuckDB (17 coins, 4 timeframes)
- 5 backtest strategies: MA Cross, RSI Mean Rev, Breakout, Bollinger, Volume Spike
- Walk-forward + purged K-fold + deflated Sharpe + ensemble voting
- Multi-provider LLM: Ollama (Qwen 8B), CommandCode (DeepSeek V4 Pro), DeepSeek, OpenAI, Groq
- Strategist LLM — VETO-ONLY (cannot originate trades)
- Analyst LLM, Sentiment Agent (Fear & Greed + RSS), Risk Manager
- SignalEngine: deterministic ensemble + meta-labeler
- Validation Gate: Pydantic schema + absolute rules enforced in code
- Paper trading + Live execution (maker-first limit → market fallback)
- Kill Switch (Telegram), Fee Tracker, FastWatchdog (600s)
- Streamlit dashboard, Telegram bot, Heartbeat (6h)
- FastAPI server on :8000 with Swagger UI
- Journal writer (LLM daily summary at 10 PM IST)

### v0.2.0 — Refinement ✅
- Trailing stop-loss (activates at 1% profit, trails at 0.5%)
- Decision memory: past 10 trades injected into Strategist LLM context
- Portfolio rotation: auto-swap weak coins for strong ones (fee-checked)
- Hurst exponent for regime detection (mean-reverting vs trending)
- HMM regime detection (GaussianHMM 3-state, trained on 250+ samples)
- Information bars: volume/dollar/tick bar conversion from time bars
- Fear & Greed backtest validation with Spearman IC + Granger causality
- Funding rate + Open Interest pipeline (DerivativesAgent, ccxt-based)
- Live Sharpe auto-de-risk (monitors live vs backtest drift, auto-sizes down)
- Meta-labeler retraining on live trade outcomes
- quantstats performance reports (HTML tear sheets + API endpoint)
- Social Sentiment Pipeline: CoinGecko + Reddit + LunarCrush data aggregation
- Social Sentiment Agent: crowd euphoria/panic detection, contrarian signals
- DuckDB `social_mentions` table for sentiment tracking over time
- Risk Manager LLM: advisory-only (Gate enforces final rules)

### v0.3.0 — Futures ✅
- FuturesGate: statistical unlock — requires 50+ spot trades, Sharpe ≥ 1.2, win rate ≥ 40%, 5+ profitable days
- FuturesTrader: USDT-M perpetuals, 1x-2x leverage, isolated margin, liquidation distance checks
- StateManager: vanilla/aggressive mode switch, auto-scaling leverage, persisted to `data/runtime_state.json`
- CUSUM-filtered bar sampling: structural break detection before price indicators
- Maker/taker SpreadOptimizer: L2 order book adaptive spreads per coin, fill-rate learning
- Futures execution routing in main loop (aggressive + gate unlocked → FuturesTrader)
- API endpoints: `GET /futures`, `POST /mode`, `GET /mode`, `GET /futures/gate`

### v1.0.0 — Production ✅
- **Tax Journal**: Indian crypto tax compliance — 30% flat (115BBH) + 1% TDS (194S), CSV export, ITR Schedule VDA, monthly breakdown. API: `GET /tax`, `GET /tax/monthly`
- **Multi-Exchange Arbitrage**: Bybit vs Binance spread scanner, simultaneous execution (2s window), auto-hedge on leg failure, DuckDB `arb_opportunities` log
- **LLM Fine-Tuning Pipeline**: Export winning agent decisions as Alpaca-format JSONL for unsloth LoRA training on Qwen 8B. Three agents: strategist, analyst, risk manager
- **Docker Compose**: One-command deploy — Kairo container + Ollama bridge + volume mounts
- **NSE Equity Pipeline**: Yahoo Finance integration for 15 Nifty 50 stocks, INR candle storage, market hours detection
- **Kairo Terminal UI**: Bloomberg/MiroFish-inspired institutional dashboard — HTML/CSS/JS with D3 force graph, ApexCharts, ThreeJS 3D terrain, GSAP animations, live API polling

### Current Stack
- **Database**: DuckDB (`data/market.db`) — candles, tickers, trades, agent_decisions, scorecard, portfolio_snapshots, fear_greed, social_mentions, arb_opportunities, nse_candles
- **LLM**: Ollama (Qwen 8B, local RTX 3070) for real-time + CommandCode Go (DeepSeek V4 Pro) for nightly research
- **Exchanges**: Bybit (primary) + Binance (secondary) via ccxt
- **API**: FastAPI on :8000 (REST + WebSocket push), 15+ endpoints
- **Dashboard**: Standalone HTML/CSS/JS terminal at `http://127.0.0.1:8000` + Streamlit fallback on :8501
- **Bot**: 2-minute trading cycle, 10 coins, 5 strategies, LLM-only VETO, hardcoded Gate enforcement

### API Endpoints
`/`, `/status`, `/health`, `/positions`, `/trades`, `/pnl`, `/agents`, `/control`, `/mode`, `/futures`, `/futures/gate`, `/dashboard`, `/dashboard-data`, `/report`, `/report/html`, `/tax`, `/tax/monthly`, `/market`, `/ws`
