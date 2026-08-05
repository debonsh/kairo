# Kairo — Improvement Roadmap

> v1.0 complete. All P0-P3 items built and integrated. This roadmap documents the journey.

## Implementation Status — v1.0 (2026-08-04)

| Item | Status |
|---|---|
| P0.1 Enforce the 48h time-stop | ✅ Built — `PositionManager` closes at 48h with `time_stop` exit reason |
| P0.2 Wire `info_bars.py` into live stream | ✅ Built — volume/dollar/CUSUM bars feed real-time signal blocks |
| P0.3 Sweep `min_confidence` | ✅ Tool built — `scripts/confidence_sweep.py`. Current threshold 0.55, re-sweep as journal grows |
| P0.4 Meta-labeler sample-size caveats | ✅ Built — `MetaLabelClassifier.training_samples` + `trusted` flag |
| P1.1 Market making | ✅ Built — `src/execution/market_maker.py`, opt-in execution path |
| P1.2 Triangular arbitrage | ✅ Built — `src/execution/triangular_arb.py`, single-exchange 3-leg loops |
| P1.3 Alpha discovery | ✅ Built — `src/backtest/alpha_search.py`, candidate generator |
| P2.1 Joint position sizing (cvxpy) | ✅ Built — `src/agents/joint_sizer.py`, correlation-aware convex allocation |
| P2.2 Fill validation for SpreadOptimizer | ✅ Built — `src/backtest/fill_validation.py`, queue-position simulation |
| P3.1 vectorbt research speed | ✅ Built — `scripts/vectorbt_search.py`, vectorized SMA/RSI sweeps |

## v1.0 Feature Modules

| Module | Purpose |
|---|---|
| `src/agents/social_sentiment.py` | Crowd euphoria/panic from CoinGecko + Reddit + LunarCrush |
| `src/agents/derivatives.py` | Funding-rate crowd detection + OI divergence sizing |
| `src/execution/arbitrage.py` | Bybit↔Binance cross-exchange spread scanner + executor |
| `src/execution/spread_optimizer.py` | L2 order-book adaptive limit offsets, fill-rate learning |
| `src/execution/futures_gate.py` | Statistical futures unlock gate (50 trades/Sharpe/WR/days) |
| `src/execution/futures_trader.py` | USDT-M perp execution, leverage, liquidation checks |
| `src/monitor/tax_journal.py` | Indian crypto tax: 30% flat + 1% TDS, CSV export |
| `src/pipeline/nse_data.py` | NSE equity OHLCV via Yahoo Finance |
| `src/learning/finetune_pipeline.py` | Export winning decisions as Alpaca JSONL for LoRA training |
| `src/config/state_manager.py` | Vanilla/aggressive hot-swap mode profiles + futures bridge |
| `src/pipeline/info_bars.py` | Volume/dollar/CUSUM information-driven bar converters |

> The `kairo/` dashboard module was removed on 2026-08-05 for a full UI redesign. The API surface (`/dashboard-data`, `/ws`) it consumed is unchanged.

## Roadmap Complete

All phases shipped:
- **v0.1**: Foundation (pipeline, backtest, strategies, agents, execution, monitoring)
- **v0.2**: Refinement (social sentiment, HMM/Hurst, info bars, F&G validation, Sharpe auto-de-risk, trailing stops, decision memory, portfolio rotation)
- **v0.3**: Futures (FuturesGate, FuturesTrader, StateManager, CUSUM bars, spread optimizer)
- **v1.0**: Production (tax journal, multi-exchange arb, LLM fine-tuning pipeline, Docker, NSE equities, institutional dashboard)
