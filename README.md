# ◆ Kairo

> Autonomous AI crypto trading system. v1.0 production.

---

## What Is Kairo?

Kairo is a fully autonomous trading bot that uses **5 deterministic strategies + an LLM agent layer** to trade crypto 24/7. It runs on your machine, costs ₹0/month, and trades via Bybit/Binance APIs (spot + gated futures).

**The LLM can VETO trades but can NEVER force one.** Every order passes through a hardcoded gate that no agent can override. This is the core safety philosophy.

## Design Philosophy

| Principle | Implementation |
|---|---|
| **LLM as filter, not executor** | SignalEngine (deterministic) generates signals. LLM only approves or vetoes. Cannot originate trades. |
| **Absolute risk rules** | `config/risk_rules.yaml` + `gate.py` — immutable by any agent, enforced at the HTTP boundary |
| **Backtest before deploy** | Walk-forward + purged K-fold + deflated Sharpe before any strategy goes live |
| **Paper → live gradually** | Paper trading default, statistical gate before live capital or futures |
| **Shadow-mode promotion** | Any learned parameter runs parallel for 50 cycles before replacing live |
| **Fail safe, not fail silent** | FastWatchdog (30s), heartbeat (6h), Telegram kill switch, auto-pause on API errors |

## Quick Start

```powershell
# 1. Install dependencies
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Pull the LLM model (free, runs on your GPU)
ollama pull qwen3:8b

# 3. Configure
cp .env.example .env
# Edit .env with your Bybit/Binance API keys + Telegram bot token

# 4. Start
.venv\Scripts\python.exe -m src.main
```

First run auto-fetches 7 days of historical data. Subsequent runs skip the fetch.

## Commands

| Command | Does |
|---|---|
| `python -m src.main` | Start trading loop (auto-fetches data if DB empty) |
| `python -m src.main --backtest` | Run backtest sweep on all strategies |
| `python -m src.main --dashboard` | Launch Streamlit dashboard at `localhost:8501` |
| `python -m src.main --validate-fng` | Validate Fear & Greed predictive value |
| `docker compose up` | One-command deploy with Ollama |

While running:
- UI: `http://127.0.0.1:8000` (blank redesign canvas — new UI in progress)
- Telegram: `/status` `/stop` `/pause` `/resume` `/mode aggressive` `/vanilla`
- API: `http://127.0.0.1:8000/docs` (Swagger UI)
- Tax: `http://127.0.0.1:8000/tax` (Indian compliance report)
- Dashboard: `http://127.0.0.1:8000/dashboard`

## LLM Architecture

Ollama (Qwen 8B, RTX 3070) handles the real-time trading hot path — Strategist filter, Analyst, Sentiment parsing. CommandCode Go (DeepSeek V4 Pro) handles nightly research, journal summaries, and prompt evolution. Both unified under one `LLMClient` with automatic fallback chain: Ollama → Groq → CommandCode → DeepSeek → OpenAI.

| Provider | Use | Cost |
|---|---|---|
| Ollama (qwen3:8b) | Real-time decisions | ₹0 — runs on RTX 3070 |
| CommandCode Go | Nightly research, journal, prompt evolver | ~₹80/month |
| DeepSeek API | Backup cloud inference | ~₹200/month |
| OpenAI (GPT-4o) | Optional fallback | Pay-per-use |
| Groq | Fast cloud inference | Free tier |

Config: `LLM_REALTIME_PROVIDER` and `LLM_RESEARCH_PROVIDER` in `.env`

## File Structure

```
TradingBot/
├── config/
│   ├── settings.yaml        # All parameters
│   ├── coins.yaml           # 17 crypto pairs
│   ├── risk_rules.yaml      # Absolute rules + vanilla/aggressive profiles
│   └── prompts/             # Agent prompt templates
├── src/
│   ├── main.py              # Entry point
│   ├── pipeline/            # Data ingestion (ccxt, Yahoo Finance, CoinGecko, Reddit, LunarCrush)
│   ├── backtest/            # Engine + 5 strategies + sweep + meta-labeling + hazard
│   ├── agents/              # LLM client + 6 agents + orchestrator + gate + signal engine
│   ├── execution/           # Exchange + paper + live + futures + arb + spread optimizer + position + killswitch
│   ├── learning/            # Scorecard + calibrator + evolver + shadow + memory + finetune pipeline
│   ├── monitor/             # Dashboard + Telegram + heartbeat + watchdog + alerter + tax journal
│   ├── config/              # State manager (vanilla/aggressive mode + leverage auto-scaling)
│   └── api/                 # FastAPI server + WebSocket push
├── docs/                    # Documentation
├── tests/                   # Test suite
├── data/                    # DuckDB (auto-created, gitignored)
├── logs/                    # Log files (gitignored)
├── Dockerfile               # Container build
├── docker-compose.yml       # One-command deploy
├── requirements.txt
├── .env.example
└── .gitignore
```

## Risk & Execution Layers

**Layer 1 — Gate (hardcoded, unchangeable)**
- Position size: 2% vanilla / 5% aggressive (profile-driven)
- Min confidence: 0.55 floor
- Hard SL/TP, min risk:reward, max 5 positions
- Pydantic schema validation on all agent outputs
- Extreme greed → block LONGs, extreme fear → block SHORTs

**Layer 2 — Risk Manager (Half-Kelly + volatility targeting)**
- Position size = min(vol-targeted, fractional Kelly, max_allowed)
- Conviction multiplier (aggressive only): scales with meta-labeler probability
- Regime multiplier: 1.5x in trends, 0.35x in high vol
- Daily loss limit: 5% → pause 24h

**Layer 3 — Calibrator (auto-de-risk)**
- Live Sharpe vs backtest drift monitoring
- Drift > 0.5 → halve position sizes
- Drift > 1.0 → emergency pause

**Layer 4 — FuturesGate (leverage is earned)**
- 50+ closed spot trades + Sharpe ≥ 1.2 + win rate ≥ 40% + 5+ profitable days
- Vanilla = spot only (1x). Aggressive + gate unlocked = up to 2x futures

**Layer 5 — Mode Profiles (hot-swap, zero restart)**
- Vanilla (conservative) and Aggressive (high-conviction) profiles
- Switch via API, Telegram, dashboard, or keyboard shortcut
- Persisted to `data/runtime_state.json` (atomic write)

**Layer 6 — SpreadOptimizer (v0.3)**
- L2 order book adaptive limit offsets per coin
- Fill-rate learning: auto-widen on low fills, tighten on high fills
- Three-stage routing: optimized limit → bid/ask → market

## Data Pipeline

| Source | What | Table |
|---|---|---|
| Bybit/Binance (ccxt) | OHLCV, tickers, order book | `candles`, `tickers` |
| Fear & Greed API | Market sentiment index | `fear_greed` |
| CoinGecko API | Market data, trending, social stats | `social_mentions` |
| Reddit (public JSON) | Hot posts from 4 crypto subs | `social_mentions` |
| LunarCrush API | Social volume, galaxy score, influencer activity | `social_mentions` |
| RSS Feeds | CryptoPanic, CoinTelegraph, CoinDesk | In-memory cache |
| Yahoo Finance | NSE equity OHLCV | `nse_candles` |

## DuckDB Schema

`candles`, `tickers`, `trades`, `agent_decisions`, `scorecard`, `portfolio_snapshots`, `fear_greed`, `social_mentions`, `arb_opportunities`, `nse_candles`, `spread_log`, `market_making`, `tri_arb_opportunities`, `info_bars`, `reliability_log`

## Strategy Ensemble

| Strategy | Best Regime | Weight |
|---|---|---|
| Moving Average Cross | Strong trend | 1.3x in trend, 0.3x in chop |
| RSI Mean Reversion | Mean-reverting | 1.5x in mean-reverting, 0.3x in trend |
| Breakout | High vol | 1.3x in high vol |
| Bollinger Reversion | Mean-reverting | 1.5x in mean-reverting |
| Volume Spike | Any vol-driven | 1.2x in any |

Weights adjust dynamically via ADX + Hurst exponent + HMM regime probabilities.

## Telegram Commands

| Command | Action |
|---|---|
| `/status` | Portfolio state, balance, open positions |
| `/positions` | List all open trades with SL/TP |
| `/pnl` | Profit/loss summary |
| `/stop` | **KILL SWITCH** — closes all positions, stops bot |
| `/pause` | Pause trading (positions stay open) |
| `/resume` | Resume trading |
| `/mode aggressive` | Switch to aggressive profile (futures if gate unlocked) |
| `/vanilla` | Switch to vanilla profile (spot only) |
| `/help` | Show all commands |

## API Endpoints

| Endpoint | Method | Returns |
|---|---|---|
| `/` | GET | UI redesign canvas (blank HTML placeholder) |
| `/health` | GET | Health check |
| `/status` | GET | Full portfolio + bot state |
| `/positions` | GET | Open positions with SL/TP |
| `/trades?limit=20` | GET | Recent trade history |
| `/pnl` | GET | P&L summary + win rate |
| `/agents` | GET | Orchestrator status |
| `/futures` | GET | Futures gate status + leverage |
| `/mode` | POST | Switch vanilla/aggressive |
| `/control` | POST | `stop` / `pause` / `resume` |
| `/dashboard` | GET | Standalone HTML dashboard |
| `/dashboard-data` | GET | Full dashboard payload (JSON) |
| `/report` | GET | Performance metrics |
| `/report/html` | GET | quantstats HTML tear sheet |
| `/tax` | GET | Tax liability (115BBH + 194S) |
| `/tax/monthly` | GET | Monthly tax breakdown |
| `/market` | GET | Live market snapshot |
| `/ws` | WebSocket | Live push channel |

## Requirements

- Python 3.11+
- Ollama (for local LLM)
- Windows/macOS/Linux
- RTX GPU (optional — Ollama runs on CPU)
- Bybit testnet account (for paper trading)
- Bybit live account (for real trading, trade-only API keys)
- Telegram bot token (for alerts)
- Docker (optional, for containerized deploy)

## Phase Status

| Phase | Status |
|---|---|
| v0.1 — Foundation (pipeline, backtest, agents, execution, learning, monitoring, API) | ✅ |
| v0.2 — Refinement (social sentiment, info bars, HMM, Hurst, Sharpe auto-de-risk, trailing stops, memory, rotation, meta retrain, F&G validation) | ✅ |
| v0.3 — Futures (FuturesGate, FuturesTrader, StateManager, CUSUM bars, spread optimizer) | ✅ |
| v1.0 — Production (tax journal, multi-exchange arb, LLM fine-tuning, Docker, NSE equities, dashboard) | ✅ |

## Indian Tax Note

Crypto gains in India: 30% flat tax (Section 115BBH), 1% TDS per transaction ≥ ₹10,000 (Section 194S). Losses cannot offset gains. Kairo auto-generates tax reports via `GET /tax` with CSV export and ITR Schedule VDA. Built into `src/monitor/tax_journal.py`.

## Credits

Architecture inspired by Inalpha, OpenTraitor, AI Hedge Fund, and the awesome-systematic-trading repository. Built by Zevu + CommandCode.
