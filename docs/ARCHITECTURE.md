# Kairo — System Architecture

> v1.0 production. Autonomous AI crypto trading system: deterministic, backtest-validated
> signal engine (5 strategies + ensemble + meta-labeling) with an LLM agent layer that can
> **VETO** trades but never force them. Trades via Bybit/Binance (spot + gated futures),
> with social sentiment, derivatives context, cross-exchange arbitrage, Indian tax
> compliance, and a Bloomberg-inspired institutional web dashboard.

---

## Signal Flow (End to End)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                                  │
│                                                                     │
│  Bybit WebSocket ──→ ccxt.pro ──→ Information Bars ──→ DuckDB      │
│  Bybit/Binance API ─→ ccxt ────→ OHLCV (live cycle inserts)        │
│  Fear & Greed API ─→ httpx ──→ Sentiment Cache + fear_greed        │
│  RSS Feeds ────────→ feedparser ──→ News Cache                     │
│  CoinGecko/Reddit/LunarCrush → SocialSentimentAgent (social_mentions)│
│  Bybit perp REST ──→ DerivativesAgent (funding rate + open interest)│
│  Yahoo Finance ────→ NSE Pipeline (nse_candles, Indian equities)    │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       STRATEGY LAYER                                │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ MA Cross     │  │ RSI Mean Rev │  │  Breakout    │              │
│  │ evaluate()   │  │ evaluate()   │  │  evaluate()  │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                       │
│  ┌──────┴───────┐  ┌──────┴───────┐         │                       │
│  │ Bollinger    │  │ Volume Spike │         │                       │
│  │ evaluate()   │  │ evaluate()   │         │                       │
│  └──────┬───────┘  └──────┬───────┘         │                       │
│         └─────────────────┴─────────────────┘                       │
│                           ↓                                         │
│              ┌────────────────────────┐                            │
│              │   StrategyEnsemble     │                            │
│              │  (regime-weighted,     │                            │
│              │   ADX/vol multipliers) │                            │
│              └───────────┬────────────┘                            │
│                          ↓                                          │
│              ┌────────────────────────┐                            │
│              │   MetaLabeler (RF)     │                            │
│              │  3:1 asymmetric        │                            │
│              │  triple-barrier labels │                            │
│              └───────────┬────────────┘                            │
│                          ↓                                          │
│              ┌────────────────────────┐                            │
│              │    SignalEngine        │                            │
│              │  {action, confidence}  │                            │
│              │  min_confidence floor  │                            │
│              │  (0.55 profile-tuned)  │                            │
│              └────────────────────────┘                            │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        AGENT LAYER                                  │
│                                                                     │
│  SignalEngine output ──→ Strategist LLM (VETO only)               │
│                               │                                     │
│                               ├── Context check: does this make     │
│                               │   sense given sentiment/news?       │
│                               │                                     │
│                               ├── Disagreement check: signal vs     │
│                               │   filter confidence → size down     │
│                               │   (0.5x) or skip (0x)               │
│                               │                                     │
│  Analyst LLM ─────────────┤                                        │
│  (reads charts, direction) │                                       │
│                               │                                     │
│  SentimentAgent ────────────┤  (Fear & Greed, RSS, backtest-        │
│  SocialSentimentAgent ──────┤   validated + crowd euphoria/panic)   │
│  DerivativesAgent ──────────┤  (crowded longs, weak-rally OI        │
│                               │   divergence → size × 0.75)         │
│                               ↓                                     │
│              ┌────────────────────────┐                            │
│              │   Risk Manager         │                            │
│              │  Half-Kelly + vol-     │                            │
│              │  targeting + conviction│                            │
│              │  (reads active profile │                            │
│              │   every tick)          │                            │
│              └───────────┬────────────┘                            │
└──────────────────────────┼──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         GATE LAYER                                  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  Pydantic Schema Validation                                  │  │
│  │  - action ∈ {LONG, SHORT, HOLD}                             │  │
│  │  - confidence ∈ [0.0, 1.0]                                  │  │
│  │  - prices positive, sizes > 0                               │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              ↓                                       │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  Absolute Rules (risk_rules.yaml base, enforced in gate.py) │  │
│  │  - Position % from active profile × micro-cap scale-up      │  │
│  │  - Min confidence floor (0.55)                              │  │
│  │  - Hard SL/TP, min risk:reward, max 5 positions             │  │
│  │  - Correlation cap vs open positions, volatility pause      │  │
│  │  - Balance floor, daily loss + drawdown kill switches       │  │
│  │  - Extreme greed → block LONGs; extreme fear → block SHORTs │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              ↓                                       │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  FuturesGate (perpetuals unlock — statistical only)         │  │
│  │  50+ closed trades ∧ Sharpe ≥ 1.2 ∧ WR ≥ 40% ∧              │  │
│  │  5+ consecutive profitable days → 2x leverage in aggressive │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      EXECUTION LAYER                                │
│                                                                     │
│  ┌──────────────────────┐                                          │
│  │  SpreadOptimizer     │  L2 order-book adaptive limit offsets,   │
│  │  (v0.3)              │  fill-rate learning per coin             │
│  └──────────┬───────────┘                                          │
│             ↓                                                        │
│  ┌──────────────────────┐     ┌──────────────────────┐             │
│  │   Paper Trader       │     │   Exchange (ccxt)     │             │
│  │   (testnet mode)     │     │   Bybit + Binance     │             │
│  └──────────────────────┘     └──────────────────────┘             │
│             ↓                                                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Position Manager                                             │  │
│  │  - Only closes on: SL / TP / trailing stop / rotation / kill │  │
│  │  - Never closes on time (48h rule configured but unenforced) │  │
│  │  - ID-based cleanup (DB dict ≠ memory dict)                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────┐   ┌──────────────────────┐              │
│  │  FuturesTrader       │   │  ArbitrageScanner    │              │
│  │  bybit perps, 1-2x   │   │  Bybit↔Binance       │              │
│  │  (mode-gated)        │   │  spread arb (2s)     │              │
│  └──────────────────────┘   └──────────────────────┘              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       LEARNING LAYER                                │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Scorecard   │  │  Calibrator  │  │   Evolver    │              │
│  │  per-trade   │──│  confidence  │──│  prompt      │              │
│  │  accuracy    │  │  adjustment  │  │  rewriting   │              │
│  └──────────────┘  └──────┬───────┘  └──────────────┘              │
│                            │                                         │
│              ┌─────────────┴─────────────┐                         │
│              │  Sharpe Drift Check        │                         │
│              │  Live vs Backtest          │                         │
│              │  Drift > 0.5 → size × 0.5 │                         │
│              │  Drift > 1.0 → pause       │                         │
│              └─────────────┬─────────────┘                         │
│                            │                                         │
│              ┌─────────────┴─────────────┐                         │
│              │  MetaLabelRetrainer        │                         │
│              │  re-trains RF on live      │                         │
│              │  outcomes as trades grow   │                         │
│              └─────────────┬─────────────┘                         │
│                            │                                         │
│              ┌─────────────┴─────────────┐                         │
│              │  Shadow Engine             │                         │
│              │  params validated 50       │                         │
│              │  cycles before promotion   │                         │
│              └───────────────────────────┘                         │
│                                                                     │
│  FinetunePipeline: exports winning agent decisions as Alpaca JSONL  │
│  (data/finetune) for LoRA fine-tuning of the local model            │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      MONITORING LAYER                               │
│                                                                     │
│  ┌──────────────────────┐   ┌──────────────────────┐              │
│  │  Kairo Dashboard     │   │  Telegram Bot        │              │
│  │  (UI redesign in     │   │  /stop /pause        │              │
│  │  progress — blank    │   │  /mode /aggressive   │              │
│  │  canvas at :8000)    │   │  /vanilla /status    │              │
│  └──────────────────────┘   └──────────────────────┘              │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  FastWatchdog│  │  API Server  │  │   Journal    │              │
│  │  (30s stall) │  │  FastAPI     │  │   (daily)    │              │
│  │              │  │  :8000       │  │              │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                     │
│  TaxJournal: Section 115BBH (30% flat) + 194S (1% TDS) compliance   │
│  exports (CSV / ITR Schedule VDA / monthly) — /tax API              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

### 1. LLM as Veto, Not Executor
The SignalEngine (deterministic, backtest-validated strategies) originates all trade proposals. The LLM's only job is to say "this makes sense" or "this doesn't make sense." It cannot generate a trade from nothing.

**Rationale:** LLMs hallucinate. A trading decision must have a backtest-validated statistical edge. The LLM provides context filtering, not alpha generation.

### 2. 3:1 Asymmetric Triple-Barrier Meta-Labeling
Each strategy signal is labeled with triple-barrier outcomes (profit target / stop loss / timeout) where the profit target is set at **3× the stop distance** (asymmetric 3:1 barriers), and a RandomForest classifier predicts whether the signal will be profitable. This model filters signals before the LLM even sees them, and the 3:1 asymmetry means even a ~35% hit rate is net profitable.

**Rationale:** Standard reference technique from López de Prado's *Advances in Financial Machine Learning*. The asymmetric barriers match the aggressive profile's 3:1 payout target (`tp_atr_multiplier: 3.0` vs `sl_atr_multiplier: 1.0`).

### 3. Regime-Conditional Weighting + Position Multipliers
Two regime levers, both driven by ADX + realized volatility (plus HMM regime probabilities):

1. **Signal weights** — strategies are up/down-weighted by detected regime before ensemble voting.
2. **Position size** — `regime_multipliers[regime]` scales the final position size (e.g. `strong_trend: 1.5` presses winners in aggressive mode; `high_vol: 0.35` near-stand-down in panic).

**Rationale:** No single strategy works in all market conditions. Dynamic weighting improves ensemble robustness, and regime-aware sizing adds a second, independent risk control.

### 4. Half-Kelly + Volatility Targeting + Conviction Sizing
Position size is the minimum of three constraints, then scaled by regime and meta-confidence:

1. **Volatility-targeted**: size = (Capital × `vol_target_risk_pct`) / (ATR × `sl_atr_multiplier`) — constant risk budget.
2. **Fractional Kelly**: `f* = (p·(b+1) − 1) / b` with `b` = TP/SL payout ratio, allocated = `min(kelly_fraction·f*, max_position_pct)`. Vanilla = ¼ Kelly (0.25), aggressive = ½ Kelly (0.50).
3. **Max allowed**: hard % of portfolio from the active profile.

Then:
- **Conviction multiplier** (aggressive only): size scales with meta-labeler probability `1 + 0.5·(p − 0.55)/0.45`, capped at 1.5×.
- **Regime multiplier** `M_regime` (see #3).
- **Micro-capital scale-up**: accounts below the balance threshold get a higher *effective* position % so single orders clear exchange minimums (USD risk still bounded).

**Rationale:** Position sizing moves risk-adjusted returns more than signal tuning. Kelly prevents overbetting, vol-targeting keeps risk constant, conviction press-winners, and micro-cap scaling keeps small accounts actually tradable.

### 5. Runtime Mode Profiles (vanilla / aggressive)
`config/risk_rules.yaml` defines base rules plus a `profiles:` section. `RuntimeStateManager` (in `src/config/state_manager.py`) deep-merges the active profile over the base and exposes `get_active_params()`:

- **Hot-swap, zero restarts** — mode flips via Telegram (`/mode`, `/aggressive`, `/vanilla`), the API (`POST /mode`), the dashboard toggle, or keyboard shortcut (`1`/`V` → vanilla, `2`/`A` → aggressive, `3`/`D` → DCA). Persisted to `data/runtime_state.json` (atomic write).
- **Thread-safe** — `threading.RLock`; a daemon poller thread syncs mode changes made by *other* processes (dashboard ↔ bot) from disk. The trading loop itself never does file I/O.
- **Every tick re-read** — RiskManager, Gate, and SignalEngine call `get_active_params()` on each evaluation, so switching mode changes live sizing immediately.
- `StateManager` (subclass) adds the **futures bridge**: vanilla forces 1× leverage / spot routing; aggressive checks FuturesGate and applies up to 2× leverage when unlocked.

| Parameter | Vanilla | Aggressive |
|---|---|---|
| max_position_pct | 2.0% | 5.0% |
| kelly_fraction | 0.25 (¼ Kelly) | 0.50 (Half-Kelly) |
| vol_target_risk_pct | 1.0% | 1.5% |
| sl / tp (ATR mult) | 2.0 / 4.0 (2:1) | 1.0 / 3.0 (asymmetric 3:1) |
| min_risk_reward | 1.5 | 2.0 |
| conviction_scale | 0 (off) | 0.5 (max 1.5×) |
| regime strong_trend mult | 1.0 | 1.5 |
| regime high_vol mult | 0.5 | 0.35 |
| micro-cap threshold / ceiling | $2,000 / 20% | $5,000 / 25% |
| futures routing | spot only (1×) | up to 2× when gate unlocks |

**Rationale:** A single global risk profile forces a false choice between conservatism and growth. Two deeply merged profiles let the operator switch the *aggressiveness* of the same battle-tested engine without a restart.

### 6. FuturesGate — Leverage Is Earned, Not Configured
Perpetuals are only unlocked by **statistical proof on the live journal**: 50+ closed trades, rolling Sharpe ≥ 1.2, win rate ≥ 40%, and 5+ consecutive profitable days. Until then, even in aggressive mode, execution stays spot (1×).

**Rationale:** Leverage amplifies mistakes. The gate conditions encode "the system has demonstrated an edge before it is allowed to borrow capital."

### 7. Shadow-Mode Parameter Promotion
Any parameter the learning layer produces (evolver, calibrator, meta-model weights) runs in parallel with live execution for 50 cycles before replacing the active parameter. No hot-swapping learned parameters into production.

**Rationale:** Same philosophy as the Gate — learned parameters don't get direct production access.

### 8. PnL Is Persisted at Close
`PaperTrader.close_position` writes `pnl` / `pnl_pct` into the DuckDB `trades` row at exit (`store.update_trade_exit`). On startup, `_restore_trade_history` reloads closed trades into the in-memory journal **and backfills** any legacy rows with NULL pnl (`UPDATE ... WHERE pnl IS NULL` — idempotent). Every DB consumer that filters on `pnl IS NOT NULL` — TaxCalculator, FuturesGate, report, memory, finetune — depends on this invariant.

**Rationale:** The dashboard feed and tax/futures analytics must agree with the DB, or the bot is flying blind. (Historical gap: pre-v1.0 closes never persisted pnl; the backfill repairs existing data once.)

### 9. v1.0 Feature Modules

| Module | Purpose | Wiring |
|---|---|---|
| `src/agents/social_sentiment.py` | Crowd euphoria/panic from CoinGecko + Reddit + LunarCrush | `orchestrator.social.prefetch()` each cycle |
| `src/agents/derivatives.py` | Funding-rate crowd detection + OI divergence sizing | `orchestrator.derivatives.get_context()` |
| `src/execution/arbitrage.py` | Bybit↔Binance cross-exchange spread scanner + simultaneous 2s-window execution, auto-hedge on leg failure | `arb_opportunities` DB log |
| `src/execution/spread_optimizer.py` | L2 order-book adaptive limit offsets, fill-rate learning | `Exchange.place_order(..., spread_optimizer=)` |
| `src/monitor/tax_journal.py` | Indian crypto tax: 115BBH 30% flat, 194S 1% TDS, CSV/ITR/monthly exports | `/tax`, `/tax/monthly` |
| `src/pipeline/nse_data.py` | NSE equity OHLCV via Yahoo Finance | `nse_candles` DB table |
| `src/learning/finetune_pipeline.py` | Export winning decisions as Alpaca JSONL for LoRA training | `data/finetune/` |
| `src/execution/futures_gate.py` + `futures_trader.py` | Statistical futures unlock + bybit perp execution | `StateManager` bridge |
| `src/execution/market_maker.py` | Market-making execution path (P1.1) — quotes both sides, inventory-skew risk rules, paper fills | `market_making` table; opt-in in settings |
| `src/execution/triangular_arb.py` | Single-exchange 3-leg triangular arb (P1.2) — detection + paper execution | `tri_arb_opportunities` table; opt-in in settings |
| `src/agents/joint_sizer.py` | cvxpy joint position sizing (P2.1) — correlation-aware allocation within Kelly/vol caps | `orchestrator` after risk sizing, before gate |
| `src/backtest/alpha_search.py` | Formulaic alpha candidate generator (P1.3) → feeds existing validation pipeline | `data/alpha_candidates.json` |
| `src/backtest/fill_validation.py` | Queue-position + latency fill simulation (P2.2) — validates SpreadOptimizer assumptions | `scripts/` + manual |

### 10. Information-Driven Bars
The pipeline supports volume bars, dollar bars, and tick bars as alternatives to time-based OHLCV. Crypto trades 24/7 with wildly uneven activity — time bars oversample dead hours and blur information-carrying bursts.

**Status:** Wired into the live stream (roadmap P0.2). `LiveStream` folds incoming 15m OHLCV into info bars (`info_bars` table, `store.insert_info_bars()`), and `_build_market_data` computes the 15m signal block from volume bars when `trading.info_bars.enabled` is on. 1h/4h/1d remain time-based. Config: `trading.info_bars.bar_type` (volume | dollar | tick | cusum).

---

## Runtime State & Threading Model

```
                ┌────────────────────────────────────────────────┐
                │           data/runtime_state.json              │
                │           {"mode": "vanilla|aggressive"}       │
                └───────────────────────┬────────────────────────┘
                                        │ atomic write / daemon poll
   ┌───────────────┐   ┌────────────────┴────────────────┐   ┌───────────────┐
   │ Telegram bot  │   │      RuntimeStateManager        │   │   Dashboard   │
   │ thread        │──▶│  RLock, get_active_params()     │◀──│   (separate   │
   │ /mode cmd     │   │  deep-merges risk_rules.yaml    │   │   process)    │
   └───────────────┘   └───────────┬─────────────────────┘   └───────────────┘
                                   │  read every tick
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
   SignalEngine             RiskManager                 Gate
   (min_confidence floor)  (kelly/vol/conviction)   (max position %)

   StateManager (subclass) adds: FuturesGate + FuturesTrader bridge —
   vanilla → 1x/spot, aggressive+unlocked → 2x/perps.
```

---

## Database Schema (DuckDB — `data/market.db`)

```
candles (exchange, symbol, timeframe, timestamp, o, h, l, c, v, trades)
tickers (exchange, symbol, timestamp, bid, ask, last, 24h stats)
trades (id, exchange, symbol, side, entry/exit price, qty, usdt value,
        entry/exit time, pnl, pnl_pct, status, sl, tp, strategy,
        agent_decision JSON, exit_reason)          -- pnl ALWAYS persisted at close
agent_decisions (id, timestamp, symbol, agent, decision JSON, snapshot JSON, latency)
scorecard (id, trade_id, predicted direction, actual direction, confidence, was_correct, agent)
portfolio_snapshots (timestamp, balance, equity, open positions, daily pnl, total pnl, drawdown%)
fear_greed (timestamp, value, classification)
social_mentions (source, symbol, timestamp, mentions, sentiment, score)
arb_opportunities (timestamp, pair, spread_pct, leg_a, leg_b, status, executed)
nse_candles (symbol, timeframe, timestamp, o, h, l, c, v)   -- Indian equities
```

---

## LLM Provider Architecture

```
                    ┌─────────────────────────────┐
                    │       LLMClient             │
                    │  ask(prompt, provider=None) │
                    │  ask_with_fallback(prompt)  │
                    └──────────┬──────────────────┘
          ┌────────────────────┼────────────────────┬───────────────┐
          ▼                    ▼                    ▼               ▼
    ┌──────────┐        ┌──────────┐        ┌──────────┐     ┌──────────┐
    │  Ollama  │        │ DeepSeek │        │  OpenAI  │     │  Groq    │
    │  (local) │        │  (API)   │        │  (API)   │     │  (API)   │
    └──────────┘        └──────────┘        └──────────┘     └──────────┘
          │
    qwen3:8b (local)   realtime: ollama | commandcode | groq | openai | deepseek
                       research:  commandcode | deepseek | openai
                       every agent has a deterministic fallback when LLM is down
```

---

## Sizing Calculation (live)

```
Input: balance, entry_price, ATR, meta-p, payout b, regime, active profile params

1. Vol-targeted:
   stop_distance = ATR × sl_atr_multiplier
   max_risk     = balance × vol_target_risk_pct
   vol_size     = max_risk / stop_distance

2. Kelly:
   f_star    = max(0, (p × (b + 1) − 1) / b)      # p = meta-labeler prob (floor 0.55)
   kelly_pct = kelly_fraction × f_star            # 0.25 vanilla | 0.50 aggressive
   kelly_size = (balance × kelly_pct) / entry_price

3. Max allowed:
   max_size   = (balance × effective_position_pct) / entry_price
   # effective_position_pct = micro_capital_effective_pct × conviction × max(M_regime,1)
   #   micro_capital_effective_pct: scale % up below balance_threshold so orders
   #     clear exchange minimums (ceiling max_position_pct)
   #   conviction = 1 + conviction_scale·(p−0.55)/0.45  (1.0 when scale=0)

4. Exchange min:
   min_size  = max(min_meaningful_order_usdt, symbol min) / entry_price

Final size = min(vol_size, kelly_size, max_size)
Reject if final_size × entry_price < min_size × entry_price
```

---

## Exit Conditions

Positions close ONLY on:
1. **Stop loss hit** — price crosses below (long) / above (short) the SL level
2. **Take profit hit** — price crosses above (long) / below (short) the TP level
3. **Trailing stop** — activates once unrealized profit ≥ `trailing_stop_activation_pct` (1%), then trails at `trailing_stop_distance_pct` (0.5%)
4. **Partial take-profit** — optional partial close at TP (`partial_tp`), the remainder rides the trend
5. **Rotation swap** — PortfolioRotator replaces a weak position with a stronger signal
6. **Kill switch** — Telegram `/stop` closes all at market (0.99 × entry)
7. **Time-stop (48h rule, enforced)** — a position held ≥ `position.max_hold_time_hours` (default 48h) is closed with reason `time_stop`. Previously configured-but-unenforced; a choppy-regime position that never hits SL/TP now can't sit open forever, occupying a position slot and tying up capital. SL/TP checks take precedence — time-stop only fires when neither did. Live profile params read per tick via the state manager (roadmap P0.1).

Positions NEVER close on:
- Market close
- External conditions
- "Just to be safe"

---

## Strategy Regime Mapping

| Regime | ADX | Volatility | Upweight | Downweight | M_regime (agg) |
|---|---|---|---|---|---|
| Strong Trend | >25 (22 agg) | Normal | MA Cross (1.3x), Breakout (1.2x) | RSI (0.3x), BB (0.4x) | 1.5x |
| Weak Trend | 20-25 | Normal | MA Cross (1.1x) | RSI (0.6x), BB (0.7x) | 1.2x |
| Choppy | <20 | Normal | RSI (1.3x), BB (1.2x) | MA Cross (0.3x), Breakout (0.4x) | 0.6x |
| High Vol | Any | >80th %ile | Breakout (1.3x), Volume (1.2x) | RSI (0.3x), BB (0.5x) | 0.35x |

Regime detection (`src/backtest/regime_detector.py`) also exposes HMM regime probabilities, which feed the meta-labeler features.

---

## API Surface (FastAPI — `:8000`)

| Endpoint | Purpose |
|---|---|
| `/` | UI redesign canvas (blank HTML placeholder, no-cache) |
| `/status`, `/positions`, `/trades`, `/pnl` | Portfolio state, open positions, closed trades, P&L |
| `/control` | `{command: stop\|pause\|resume}` |
| `/mode` | `{command: vanilla\|aggressive}` — hot mode switch |
| `/candles?symbol=&timeframe=&limit=` | Real OHLCV from DuckDB (freshest N) |
| `/market` | Ticker snapshot, Fear & Greed, total market cap (real web data, TTL-cached) |
| `/futures` | Mode, FuturesGate evaluation, futures trader status |
| `/report`, `/report/html` | Trade metrics report + HTML generation |
| `/tax`, `/tax/monthly` | Indian tax liability, CSV / ITR Schedule VDA / monthly summary |
| `/dashboard-data` | Full dashboard payload (equity curve, strategies, live feed, correlations, futures) |
| `/ws` | WebSocket push — full payload on connect + on every `invalidate_dashboard()` bump |
| `/agents`, `/health` | Orchestrator status, liveness |

The UI was removed for a full redesign. `src/api/server.py` now serves a blank canvas at `/` — create `index.html` in the project root and it will be served there. The JSON/WebSocket surface it consumes is unchanged: `/dashboard-data` and the `/ws` push channel (live candles, trade feed, correlation network, mode toggle via `POST /mode`). Cached payloads are keyed by an internal version counter so N open tabs share one build (rebuilt under `_payload_lock` so the shared DuckDB connection never races the trading loop's writes).

The terminal shows **real data only** — no invented demo numbers; missing data renders honest empty states (`--`, `NO DATA`). A control bar (pause/resume/stop via `POST /control`, confirmed before stop) plus a PAPER/LIVE badge show bot state; a `--scale` density toggle (S/M/L) rescales the whole layout for smaller screens. Roadmap panels expose market maker (fills/inventory/PnL), tri-arb (loops/profit), joint sizer (last solve) and the min-confidence sweep verdict; live positions are marked to market against `data/market_snapshot.json`, and the equity curve/risk stats come from real `portfolio_snapshots` history. Trade closes raise silent toasts (no sound).

---

## Key Files

| File | Role |
|---|---|
| `src/main.py` | Entry point — wiring, live loop, seeding + restore, market snapshot, backups |
| `src/agents/orchestrator.py` | Central coordinator: SignalEngine → LLM filter → Risk → Gate → Execute |
| `src/agents/signal_engine.py` | Deterministic ensemble + meta-label filter + confidence floor |
| `src/agents/gate.py` | Absolute rules — IMMUTABLE, no LLM override |
| `src/agents/risk_manager.py` | Half-Kelly + vol targeting + conviction, reads profile per tick |
| `src/config/state_manager.py` | RuntimeStateManager / StateManager — hot mode profiles + futures bridge |
| `src/execution/futures_gate.py` | Statistical perpetual-unlock gate |
| `src/agents/llm_client.py` | Multi-provider router (Ollama, DeepSeek, OpenAI, Groq, CommandCode) |
| `src/api/server.py` | FastAPI + WS push + dashboard payload builder |
| `index.html` | New UI entry point — served at `/` (create it for the redesign) |
| `config/risk_rules.yaml` | Base rules + vanilla/aggressive profiles |
| `config/settings.yaml` | All non-risk parameters |
| `src/monitor/tax_journal.py` | Indian crypto tax compliance |
