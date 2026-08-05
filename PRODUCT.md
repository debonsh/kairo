# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Solo operator:** Devan, a retail crypto trader in India. Runs Kairo on their own hardware (Windows with RTX 3070) and monitors positions throughout the day. They want autonomy — the bot trades 24/7 while they check in periodically via dashboard, Telegram, and API. This is a personal tool, not a multi-tenant product.

## Product Purpose

Kairo is an autonomous AI crypto trading bot that uses 5 deterministic strategies + an LLM agent layer to trade 24/7. The LLM can VETO trades but can NEVER force one — every order passes through a hardcoded gate that no agent can override. The bot trades spot + gated futures on 17 crypto pairs via Bybit/Binance, with built-in Indian tax compliance.

Success means: profitable, risk-managed trading that runs autonomously. The user should be able to leave it running and trust that safety constraints hold.

## Positioning

**Safety-first autonomous trading.** The core differentiator is the Gate + SignalEngine architecture: strategies originate signals deterministically, the LLM only VETOs, and hardcoded rules at the HTTP boundary can never be overridden by any agent. No other retail trading bot in this class enforces this at the code level.

Additional claims:
- ₹0/month recurring cost — runs on local GPU (Ollama/Qwen 8B)
- Indian crypto tax compliance built in (30% Section 115BBH + 1% TDS Section 194S, CSV export)
- Multi-strategy ensemble with dynamic ADX/Hurst/HMM regime weighting
- Futures leverage is earned (FuturesGate: 50+ spot trades + Sharpe ≥ 1.2 + WR ≥ 40%)

## Operating Context

- Runs on Windows/macOS/Linux — currently deployed on a Windows desktop with RTX 3070
- Traders check in via: dashboard (http://127.0.0.1:8000), Telegram commands, API/Swagger
- Trading is 24/7; positions stay open across cycles
- 2-minute trading cycle, 10 coins active, 5 max concurrent positions
- Ollama must be running locally for real-time LLM inference
- Docker optional for containerized deploy
- DuckDB (`data/market.db`) is the embedded database — delete to force re-fetch

## Capabilities and Constraints

**Capabilities:**
- 5 live strategies: MA Cross, RSI Mean Reversion, Breakout, Bollinger Reversion, Volume Spike
- Regime detection: ADX + Hurst exponent + HMM
- LLM VETO filter with multi-provider fallback (Ollama → Groq → CommandCode → DeepSeek → OpenAI)
- Social sentiment: CoinGecko + Reddit + LunarCrush + RSS feeds
- Risk management: Half-Kelly sizing, vol targeting, daily loss limits, Sharpe drift auto-de-risk
- SpreadOptimizer: L2 order book adaptive spreads with fill-rate learning
- Market making (opt-in), triangular arbitrage (opt-in)
- Tax journal with CSV export for Indian ITR
- Telegram kill switch, heartbeat monitoring, FastWatchdog
- Paper trading with fee simulation
- Backtest sweep, walk-forward validation, meta-labeling

**Constraints:**
- 5 max concurrent positions
- 2% vanilla / 5% aggressive position size (profile-driven)
- Min confidence: 0.55
- Daily loss limit: 5% → auto-pause 24h
- Futures locked behind FuturesGate (50+ spot trades + Sharpe ≥ 1.2 + WR ≥ 40% + 5+ profitable days)
- Max 2x leverage even with gate unlocked
- 48h max hold time enforced per position

**Tradeable pairs (17):** BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, DOT, ARB, OP, SUI, FET, RENDER, TIA, SEI (+ more configurable)

**Undecided:**
- Long-term hosting/deployment strategy

## Brand Commitments

Pending — user will provide design inspiration and visual direction for Kairo's UI.

## Evidence on Hand

- **Live codebase:** Full trading system with 15+ agents, 5 strategies, DuckDB schema, FastAPI, dashboard
- **Dashboard:** Standalone HTML/CSS/JS terminal at `/dashboard`, Streamlit fallback at :8501
- **UI reference:** The user has shared screenshots of Bloomberg/MiroFish quant-terminal aesthetics as design direction
- **Taste file:** Extensive UI preferences documented — dark themes, dot-matrix typography, draggable float-grid layouts, pixel-perfect fidelity
- **No real testimonials, case studies, or press.** Do not fabricate.

## Product Principles

1. **Safety is non-negotiable.** The Gate exists in code, not in prompts. Every safety layer is hardcoded and immutable by any agent.
2. **Autonomy with oversight.** The bot trades 24/7, but the user stays informed via real-time dashboard, Telegram, and API.
3. **Frugal by design.** Zero recurring subscription cost. Runs on owned hardware. Free data providers exhausted before paid ones are considered.
4. **India-aware.** Tax compliance, INR currency support, and local crypto regulations are first-class concerns.
5. **Transparent decision-making.** Every trade, VETO, and risk adjustment is logged and queryable. The LLM's influence is bounded and auditable.

## Accessibility & Inclusion

Undecided. No specific accessibility requirements or standards have been established.
