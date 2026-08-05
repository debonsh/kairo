# Kairo — Agent Context

## Project Overview
Kairo is an autonomous AI crypto trading system. v1.0 production. Uses a deterministic signal engine (5 backtest-validated strategies + ensemble voting) with an LLM agent layer that can VETO trades but never force them. Trades via Bybit/Binance with futures support, social sentiment analysis, and Indian tax compliance.

**The LLM can VETO trades but can NEVER force one.** Every order passes through a hardcoded Gate that no agent can override.

Read `README.md` for the full picture and `CHANGELOG.md` for version history.

## Architecture
See `docs/ARCHITECTURE.md` for detailed system design.

## Stack
- **Database**: DuckDB (`data/market.db`) — embedded, zero-config, columnar analytical engine
- **LLM**: Ollama (Qwen 8B, RTX 3070) for real-time + CommandCode Go (DeepSeek V4 Pro) for nightly research
- **Exchanges**: Bybit (primary) + Binance (secondary) via ccxt
- **API**: FastAPI on :8000 (REST + WebSocket), 15+ endpoints
- **Dashboard**: Standalone HTML/CSS/JS terminal + Streamlit fallback on :8501
- **Bot**: 2-minute cycle, 10 coins, 5 strategies, LLM VETO only

## Key Files
- `src/main.py` — Entry point. Starts everything.
- `src/agents/orchestrator.py` — Central coordinator. SignalEngine → LLM filter → Risk → Gate → Execute. Social sentiment + derivatives + memory all injected here.
- `src/agents/gate.py` — Absolute rules. IMMUTABLE. No LLM can override.
- `src/agents/signal_engine.py` — Deterministic signal generator. The LLM cannot originate trades.
- `src/agents/llm_client.py` — Multi-provider router (Ollama, CommandCode, DeepSeek, OpenAI, Groq).
- `src/agents/social_sentiment.py` — Crowd euphoria/panic detection from CoinGecko + Reddit + LunarCrush.
- `src/agents/sentiment.py` — Fear & Greed + RSS news sentiment.
- `src/agents/strategist.py` — LLM VETO filter, receives social context + memory + analysis.
- `src/agents/risk_manager.py` — Vol-targeted + Kelly sizing. LLM advisory-only.
- `src/agents/derivatives.py` — Funding rate + OI context for futures risk.
- `src/backtest/strategies/` — 5 strategies with backtrader + static evaluate() methods.
- `src/backtest/regime_detector.py` — ADX + Hurst + HMM regime classification.
- `src/execution/exchange.py` — ccxt wrapper with SpreadOptimizer three-stage order routing.
- `src/execution/futures_gate.py` — Statistical gate: 50 trades + Sharpe + WR + profit days.
- `src/execution/futures_trader.py` — USDT-M perp execution with liquidation checks.
- `src/execution/spread_optimizer.py` — L2 order book adaptive spreads, fill-rate learning.
- `src/execution/arbitrage.py` — Bybit vs Binance cross-exchange arb scanner + executor.
- `src/execution/position.py` — Stop-loss, take-profit, trailing stop enforcement.
- `src/execution/paper.py` — Paper trading simulator with fee deduction.
- `src/learning/finetune_pipeline.py` — Export winning decisions as Alpaca JSONL for LoRA training.
- `src/learning/scorecard.py` — Agent prediction accuracy tracking.
- `src/learning/calibrator.py` — Confidence adjustment + Sharpe drift auto-de-risk.
- `src/learning/memory.py` — Past trade outcomes injected into LLM context.
- `src/monitor/tax_journal.py` — Indian crypto tax compliance (30% + 1% TDS, CSV export).
- `src/pipeline/social_data.py` — CoinGecko + Reddit + LunarCrush data providers.
- `src/pipeline/info_bars.py` — Volume/dollar/CUSUM bar converters.
- `src/pipeline/nse_data.py` — NSE equity pipeline via Yahoo Finance.
- `src/pipeline/schema.py` — All DuckDB table schemas.
- `src/config/state_manager.py` — Vanilla/aggressive mode + leverage auto-scaling.
- `config/settings.yaml` — All parameters.
- `config/risk_rules.yaml` — Hardcoded risk limits + runtime profiles.
- `config/prompts/` — LLM prompt templates for analyst, strategist, risk manager.
- `config/coins.yaml` — 17 tracked crypto pairs.

## Code Style Guidelines
- Use descriptive variable names
- Follow existing patterns in the codebase
- Extract complex conditions into meaningful boolean variables
- All new parameters go in settings.yaml, not hardcoded
- LLM prompts live in config/prompts/, not in agent code
- Every agent has a deterministic fallback for when LLM is unavailable
- Risk-related code reads from risk_rules.yaml, never hardcodes limits

## Architecture Notes
- The LLM is a filter, NOT an executor. Trades originate from the deterministic SignalEngine.
- Gate rules are enforced at the code level (Pydantic schema + hard checks), not in prompts.
- Strategy classes have both `backtrader.Strategy` inheritance AND static `evaluate()`.
- SignalEngine registers strategy CLASSES (not instances) to avoid Cerebro dependency.
- PositionManager closes positions only on SL/TP hits, never on time.
- Social data fetched once per cycle (batch), cached for 10 min, injected as contrarian signal.
- FutureGate requires 50+ spot trades with good stats before allowing 2x leverage.
- StateManager persists mode to disk — survices restarts, shared between bot + dashboard.
- SpreadOptimizer learns from fill rates over time — auto-widens/tightens per coin.

## Common Workflows
- `python -m src.main` — Start trading (auto-fetches data on first run)
- `python -m src.main --backtest` — Run backtest sweep
- `python -m src.main --dashboard` — Launch Streamlit dashboard
- `python -m src.main --validate-fng` — Validate Fear & Greed predictive value
- `streamlit run src/ui/dashboard.py` — Launch Nothing Dot-Matrix dashboard
- `docker compose up` — One-command deploy with Ollama
- API at `http://127.0.0.1:8000/docs` for Swagger UI
- Dashboard: `http://127.0.0.1:8000/dashboard`
- UI: `http://127.0.0.1:8000` (blank redesign canvas — build the new UI here)
- Telegram bot at the configured token for commands/alerts
- Ollama must be running for local LLM (`ollama serve`)
- DuckDB file at `data/market.db` — delete to force re-fetch
- Delete `data/runtime_state.json` to reset mode to vanilla

## Testing
- `pytest tests/` — Run test suite
- `python tests/test_position.py` — Position management tests

## API Endpoints
| Endpoint | Method | Returns |
|---|---|---|
| `/` | GET | UI redesign canvas (blank HTML placeholder) |
| `/health` | GET | Health check |
| `/status` | GET | Portfolio + bot state |
| `/positions` | GET | Open positions with SL/TP |
| `/trades?limit=20` | GET | Recent trade history |
| `/pnl` | GET | P&L summary + win rate |
| `/agents` | GET | Orchestrator status |
| `/futures` | GET | Futures gate status + leverage |
| `/mode` | POST | Switch vanilla/aggressive |
| `/control` | POST | stop/pause/resume |
| `/dashboard-data` | GET | Full dashboard payload (JSON) |
| `/dashboard` | GET | Standalone HTML dashboard |
| `/report` | GET | Performance metrics |
| `/report/html` | GET | quantstats HTML tear sheet |
| `/tax` | GET | Tax liability (115BBH + 194S) |
| `/tax/monthly` | GET | Monthly tax breakdown |
| `/market` | GET | Live market snapshot |
| `/ws` | WebSocket | Live push channel |
| `/docs` | GET | Swagger UI |

## Database Tables
`candles`, `tickers`, `trades`, `agent_decisions`, `scorecard`, `portfolio_snapshots`, `fear_greed`, `social_mentions`, `arb_opportunities`, `nse_candles`

---

## Ponytail — Lazy Senior Dev Mode (always-on ruleset)

You are a lazy senior developer. Lazy means efficient, not careless. The best code is the code never written.

Before writing any code, stop at the first rung that holds:
1. Does this need to be built at all? (YAGNI)
2. Does it already exist in this codebase? Reuse the helper, util, or pattern that's already here, don't re-write it.
3. Does the standard library already do this? Use it.
4. Does a native platform feature cover it? Use it.
5. Does an already-installed dependency solve it? Use it.
6. Can this be one line? Make it one line.
7. Only then: write the minimum code that works.

The ladder runs after you understand the problem, not instead of it: read the task and the code it touches, trace the real flow end to end, then climb.

Bug fix = root cause, not symptom: a report names a symptom. Grep every caller of the function you touch and fix the shared function once — one guard there is a smaller diff than one per caller, and patching only the path the ticket names leaves a sibling caller still broken.

Rules:
- No abstractions that weren't explicitly requested.
- No new dependency if it can be avoided.
- No boilerplate nobody asked for.
- Deletion over addition. Boring over clever. Fewest files possible.
- Shortest working diff wins, but only once you understand the problem. The smallest change in the wrong place isn't lazy, it's a second bug.
- Question complex requests: "Do you actually need X, or does Y cover it?"
- Pick the edge-case-correct option when two stdlib approaches are the same size — lazy means less code, not the flimsier algorithm.
- Mark deliberate simplifications that cut a real corner with a known ceiling (global lock, O(n²) scan, naive heuristic) with a `ponytail:` comment naming the ceiling and upgrade path.

Not lazy about: understanding the problem (read it fully and trace the real flow before picking a rung — a small diff you don't understand is just laziness dressed up as efficiency), input validation at trust boundaries, error handling that prevents data loss, security, accessibility, anything explicitly requested. Lazy code without its check is unfinished: non-trivial logic leaves ONE runnable check behind — the smallest thing that fails if the logic breaks (an assert-based demo/self-check or one small test file; no frameworks, no fixtures). Trivial one-liners need no test.
