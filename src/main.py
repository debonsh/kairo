"""Kairo — Autonomous AI Crypto Trading System.

Usage:
    python -m src.main                    # Start live trading loop
    python -m src.main --backtest         # Run backtest sweep
    python -m src.main --dashboard        # Launch dashboard
"""

import sys
import os
import time
import threading
from pathlib import Path

import numpy as np
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv
import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

logger.add("logs/tradingbot.log", rotation="10 MB", retention="30 days", level="INFO")


def main():
    load_dotenv()

    from src.pipeline.store import MarketStore
    from src.pipeline.historical import HistoricalFetcher, load_coins
    from src.agents.llm_client import LLMClient
    from src.agents.signal_engine import SignalEngine
    from src.agents.orchestrator import AgentOrchestrator
    from src.agents.rotator import PortfolioRotator
    from src.backtest.meta_labeling import MetaLabelClassifier
    from src.execution.exchange import Exchange
    from src.execution.paper import PaperTrader
    from src.execution.live import LiveTrader
    from src.execution.killswitch import KillSwitch
    from src.execution.position import PositionManager
    from src.execution.fee_tracker import FeeTracker
    from src.execution.futures_gate import FuturesGate
    from src.execution.futures_trader import FuturesTrader
    from src.config.state_manager import StateManager
    from src.learning.scorecard import SignalScorecard
    from src.learning.calibrator import ConfidenceCalibrator
    from src.learning.evolver import PromptEvolver
    from src.learning.shadow import ShadowEngine
    from src.monitor.heartbeat import Heartbeat
    from src.monitor.fast_watchdog import FastWatchdog
    from src.monitor.telegram_bot import TelegramBot
    from src.monitor.alerter import Alerter
    import yaml

    with open("config/settings.yaml") as f:
        settings = yaml.safe_load(f)

    store = MarketStore()
    coins = load_coins()
    timeframes = settings["trading"]["timeframes"]
    initial_balance = 5000.0

    # Auto-fetch historical data if DB is empty
    result = store.conn.execute("SELECT COUNT(*) FROM candles").fetchone()
    if result and result[0] == 0:
        logger.info("DB empty — auto-fetching 7 days of historical data...")
        fetcher = HistoricalFetcher(store)
        fetched = fetcher.fetch_recent(coins, timeframes)
        total = sum(fetched.values())
        logger.success(f"Auto-fetched {total} candles across {len(coins)} coins")
    else:
        logger.info(f"DB has {result[0] if result else 0} candles — skipping fetch")

    if "--validate-fng" in sys.argv:
        run_fng_validation(store, settings)

    llm = LLMClient()
    try:
        llm.ask("test", "Reply 'OK'.", temperature=0.0, max_tokens=5)
        logger.info(f"LLM connected: {llm.provider}")
    except Exception as e:
        logger.warning(f"LLM unavailable: {e} — deterministic fallback active")

    from src.backtest.strategies.ma_cross import MovingAverageCross
    from src.backtest.strategies.rsi_meanrev import RSIMeanReversion
    from src.backtest.strategies.breakout import Breakout
    from src.backtest.strategies.bollinger_revert import BollingerReversion
    from src.backtest.strategies.volume_spike import VolumeSpike

    strategies = [
        MovingAverageCross,
        RSIMeanReversion,
        Breakout,
        BollingerReversion,
        VolumeSpike,
    ]

    from src.config.state_manager import RuntimeStateManager

    state_manager = RuntimeStateManager()
    state_manager.start()  # daemon poller: syncs dashboard/Telegram mode flips

    info_cfg = settings.get("trading", {}).get("info_bars", {})
    _set_info_bar_config(bool(info_cfg.get("enabled", True)),
                         str(info_cfg.get("bar_type", "volume")))

    meta_labeler = MetaLabelClassifier()
    signal_engine = SignalEngine(meta_labeler, state_manager=state_manager)
    signal_engine.register_strategies(strategies)
    logger.info(f"Runtime mode: {state_manager.get_mode()}")

    paper = PaperTrader(store, initial_balance=initial_balance)
    _restore_trade_history(paper, store)  # feed persists across restarts
    exchange = Exchange(testnet=settings["trading"]["mode"] == "paper")

    futures_gate = FuturesGate(store, mode="vanilla")
    futures_trader = FuturesTrader(
        exchange_id=settings.get("exchanges", {}).get("primary", "bybit"),
        testnet=settings.get("exchanges", {}).get("testnet", True),
        leverage=1.0,
    )
    state = StateManager(futures_gate=futures_gate, futures_trader=futures_trader)

    live = LiveTrader(store, exchange, paper)
    killswitch = KillSwitch(paper, live)
    positions = PositionManager(store, state_manager=state_manager)
    fee_tracker = FeeTracker()

    orchestrator = AgentOrchestrator(llm, store, signal_engine, state_manager=state_manager)
    orchestrator.derivatives.crowd_threshold = (
        settings.get("derivatives", {}).get("funding_crowd_annualized_pct", 30.0)
    )
    orchestrator.risk_manager._vol_alpha = settings.get("risk", {}).get("vol_ewma_alpha", 0.3)

    from src.learning.meta_retrain import MetaLabelRetrainer
    meta_trust = settings.get("backtest", {}).get("meta_label_min_samples", 100)
    retrainer = MetaLabelRetrainer(store, meta_labeler, min_trusted_samples=int(meta_trust))

    rotator = PortfolioRotator(fee_pct=0.001)

    scorecard = SignalScorecard(store)
    calibrator = ConfidenceCalibrator(store)
    evolver = PromptEvolver(llm, store)
    shadow = ShadowEngine()

    tele_bot = TelegramBot(killswitch, paper, state_manager=state_manager)

    if settings.get("monitor", {}).get("telegram_alerts", True):
        tele_chat = os.getenv("TELEGRAM_CHAT_ID", "")
        if tele_chat and tele_chat != "your_telegram_user_id":
            try:
                killswitch.add_authorized_user(int(tele_chat))
                threading.Thread(target=tele_bot.run_sync, daemon=True).start()
                logger.info("Telegram bot started")
            except ValueError:
                logger.warning("Invalid Telegram chat ID — alerts disabled")
        else:
            logger.info("Telegram not configured — alerts disabled")

    alerter = Alerter(telegram_bot=tele_bot)
    if alerter.is_configured():
        alerter.alert_startup()

    watchdog = FastWatchdog(
        stall_threshold_seconds=settings.get("monitor", {}).get("stall_threshold_seconds", 600),
        telegram_bot=tele_bot,
        alerter=alerter,
        killswitch=killswitch,  # paused/stopped loops are intentional, not stalls
    )
    watchdog.start()

    heartbeat = Heartbeat(
        interval_hours=settings.get("monitor", {}).get("heartbeat_interval_hours", 6),
        telegram_bot=tele_bot,
    )

    # Roadmap P1.1/P1.2 — market maker + triangular arb (opt-in, paper-first).
    # Created BEFORE the API server so the dashboard can expose their state.
    from src.execution.market_maker import MarketMaker
    from src.execution.triangular_arb import TriangularArbitrage

    mm_cfg = settings.get("market_making", {})
    market_maker = None
    if mm_cfg.get("enabled", False):
        mm_symbols = mm_cfg.get("symbols") or coins[:6]
        market_maker = MarketMaker(store, symbols=mm_symbols, state_manager=state_manager)
        logger.info(f"Market maker enabled on {mm_symbols}")

    ta_cfg = settings.get("triangular_arb", {})
    tri_arb = None
    if ta_cfg.get("enabled", False):
        tri_arb = TriangularArbitrage(exchange, store=store, paper_trader=paper)
        logger.info("Triangular arb scanner enabled")

    # Start API server for CommandCode / external tools / dashboard
    paper_mode = settings["trading"]["mode"] == "paper"
    _start_api_server(store, paper, orchestrator, killswitch, state=state, futures_trader=futures_trader,
                      market_maker=market_maker, tri_arb=tri_arb, paper_mode=paper_mode)

    if "--dashboard" in sys.argv:
        import subprocess
        dash_path = Path(__file__).parent / "monitor" / "dashboard.py"
        subprocess.run([
            ".venv\\Scripts\\python.exe", "-m", "streamlit", "run",
            str(dash_path), "--server.port", "8501",
            "--browser.serverAddress", "localhost",
            "--theme.base", "dark",
            "--theme.primaryColor", "#00ff88",
            "--theme.backgroundColor", "#0a0a0f",
            "--theme.secondaryBackgroundColor", "#12121a",
            "--theme.textColor", "#cdd6f4",
        ])
        return

    if "--backtest" in sys.argv:
        run_backtest_sweep(store, settings)
        return

    run_live_mode(
        store, paper, live, orchestrator, rotator, killswitch, positions,
        scorecard, calibrator, evolver, shadow, fee_tracker,
        watchdog, heartbeat, coins, settings,
        retrainer=retrainer, tele_bot=tele_bot, alerter=alerter,
        state=state, futures_trader=futures_trader,
        market_maker=market_maker, tri_arb=tri_arb,
    )


def run_live_mode(store, paper, live, orchestrator, rotator, killswitch, positions,
                  scorecard, calibrator, evolver, shadow, fee_tracker,
                  watchdog, heartbeat, coins, settings,
                  retrainer=None, tele_bot=None, alerter=None, state=None, futures_trader=None,
                  market_maker=None, tri_arb=None):
    logger.info("Starting live trading loop...")
    from src.api.server import invalidate_dashboard

    cycle_seconds = settings.get("trading", {}).get("cycle_seconds", 120)

    # Populate the paper journal once so the dashboard feed / strategy stats /
    # equity curve have data to show (real ticker prices, simulated round trips).
    if settings.get("seeding", {}).get("seed_paper_trades", True) and paper.get_portfolio()["total_trades"] == 0:
        seeded = _seed_paper_trades(paper, live.exchange, settings, store=store)
        if seeded:
            invalidate_dashboard()  # push the fresh feed to dashboard clients

    import os
    from datetime import datetime

    daily_summary_time = str(settings.get("monitor", {}).get("daily_summary_time", "22:00"))
    try:
        summary_hour = int(daily_summary_time.split(":")[0])
    except ValueError:
        logger.warning(f"Invalid daily_summary_time '{daily_summary_time}' — defaulting to 22:00")
        summary_hour = 22

    import asyncio

    api_error_threshold = settings.get("reliability", {}).get("api_error_pause_threshold", 5)
    reconcile_seconds = settings.get("reliability", {}).get("reconcile_minutes", 30) * 60
    backup_interval_seconds = settings.get("reliability", {}).get("backup_interval_hours", 24) * 3600
    healthchecks_url = (os.getenv("HEALTHCHECKS_URL", "")
                        or settings.get("reliability", {}).get("healthchecks_url", ""))
    healthchecks_interval = settings.get("reliability", {}).get("healthchecks_interval_minutes", 10) * 60
    last_reconcile = time.time()
    last_backup = time.time()
    last_healthcheck = time.time()

    if settings.get("reliability", {}).get("backup_on_startup", True):
        _backup_db(store)
        last_backup = time.time()

    trade_count = 0
    last_journal_day = None
    last_heartbeat = time.time()
    last_evolution_check = 0
    last_sharpe_check = 0

    try:
        while True:
            if not killswitch.trading_allowed():
                time.sleep(5)
                continue

            watchdog.ping_cycle()
            portfolio = paper.get_portfolio()
            current_prices = {}
            rotator.clear()

            # Prefetch social sentiment with timeout guard
            try:
                orchestrator.social.prefetch(coins[:10])
            except Exception as e:
                logger.warning(f"Social prefetch error (non-fatal): {e}")

            for coin in coins[:10]:
                try:
                    ticker = live.exchange.fetch_ticker(coin)
                except Exception:
                    ticker = None
                if not ticker or "last" not in ticker:
                    continue

                current_prices[coin] = ticker["last"]
                market_data = _build_market_data(live.exchange, coin, store=store)
                decision = orchestrator.run_cycle(coin, market_data, portfolio)

                if decision.get("action") != "HOLD":
                    trade_data = decision.get("trade") or {}
                    rotator.update_scores(
                        coin, decision["action"], decision.get("confidence", 0),
                        regime=trade_data.get("regime", "unknown"),
                    )

                if decision.get("executable") and decision.get("trade"):
                    use_futures = (
                        state is not None
                        and state.should_use_futures(decision.get("action", "LONG"))
                        and futures_trader is not None
                    )
                    if use_futures:
                        trade = _execute_futures(futures_trader, decision)
                    else:
                        trade = live.execute(decision)
                    if trade:
                        trade_count += 1
                        fee_tracker.record(
                            str(trade.get("id", "")),
                            trade.get("entry_price", 0),
                            trade.get("entry_price", 0),
                            trade.get("quantity", 0),
                            0,
                        )
                        _record_learning(scorecard, decision, trade)
                        invalidate_dashboard()  # push new trade to dashboard WS clients

                before_open = len(portfolio.get("open_trades", []))
                positions.check_exits(current_prices, paper)
                if len(paper.get_portfolio().get("open_trades", [])) != before_open:
                    invalidate_dashboard()  # a position closed — refresh dashboard
                watchdog.ping_price_stream()
                time.sleep(2)

                # API-error circuit breaker: auto-pause on consecutive failures
                if live.exchange.consecutive_errors >= api_error_threshold:
                    logger.critical(f"{live.exchange.consecutive_errors} consecutive API errors — auto-pausing")
                    killswitch.handle_command("/pause", 0)
                    alerter.alert_api_error(live.exchange.consecutive_errors)
                    break

            # Order reconciliation (live mode): exchange vs local state
            if time.time() - last_reconcile > reconcile_seconds:
                status = live.reconcile()
                logger.info(f"Reconcile: {status}")
                last_reconcile = time.time()

            # Roadmap P1.1 — market maker cycle (paper fills, inventory mgmt)
            if market_maker and current_prices:
                try:
                    mm_fills = market_maker.cycle(current_prices)
                    if mm_fills:
                        invalidate_dashboard()
                except Exception as e:
                    logger.debug(f"Market maker cycle skipped: {e}")

            # Roadmap P1.2 — triangular arb scan (single-exchange 3-leg loops)
            if tri_arb:
                try:
                    bases = sorted({c.split("/")[0] for c in coins[:8]})
                    opps = tri_arb.scan(bases)
                    for opp in opps[:2]:
                        tri_arb.execute(opp)
                except Exception as e:
                    logger.debug(f"Tri-arb scan skipped: {e}")

            # Retrain meta-labeler on real outcomes as trades accumulate
            if retrainer:
                try:
                    rt = retrainer.maybe_retrain()
                    if rt.get("trained"):
                        logger.success(f"Meta-labeler retrained: {rt}")
                except Exception as e:
                    logger.warning(f"Meta retrain skipped: {e}")

            # DB backup — cheap insurance against corruption
            if time.time() - last_backup > backup_interval_seconds:
                _backup_db(store)
                last_backup = time.time()

            # External dead-man's switch (healthchecks.io): pings stop if machine dies
            if healthchecks_url and time.time() - last_healthcheck > healthchecks_interval:
                try:
                    httpx.get(healthchecks_url, timeout=10)
                    last_healthcheck = time.time()
                except Exception as e:
                    logger.warning(f"Healthcheck ping failed: {e}")

            # Portfolio Rotation — swap weak positions for strong ones
            swaps = rotator.evaluate(portfolio, current_prices)
            for swap in swaps:
                logger.info(
                    f"Rotation: selling {swap['sell_symbol']} (conf {swap['sell_current_conf']}) "
                    f"→ buying {swap['buy_symbol']} (conf {swap['buy_conf']}, "
                    f"delta {swap['score_delta']})"
                )
                for trade in portfolio.get("open_trades", []):
                    if trade.get("symbol") == swap["sell_symbol"]:
                        sell_price = current_prices.get(swap["sell_symbol"], 0)
                        if sell_price > 0:
                            paper.close_position(trade, sell_price, "rotation_swap")
                        break

            now = datetime.now()
            today = now.date()

            if last_journal_day != today and now.hour >= summary_hour:
                from src.agents.journal import DailyJournal
                journal = DailyJournal(orchestrator.llm, store)
                text = journal.generate()
                logger.info(f"Journal:\n{text}")
                last_journal_day = today

            if time.time() - last_heartbeat > heartbeat.interval_hours * 3600:
                status = heartbeat.check(orchestrator, paper)
                if status["warnings"]:
                    import asyncio
                    asyncio.run(heartbeat.send_heartbeat(status))
                    alerter.alert("Health Warning", "; ".join(status["warnings"]), severity="warning")
                last_heartbeat = time.time()

            if trade_count - last_evolution_check >= 20:
                for agent_name in ["analyst", "strategist"]:
                    evolver.evolve(agent_name)
                last_evolution_check = trade_count

            fee_drift = fee_tracker.check_drift()
            if fee_drift["action"] == "pause_trading":
                killswitch.handle_command("/pause", 0)
                logger.critical("Trading paused — fee drift critical")

            if trade_count - last_sharpe_check >= 10:
                live_sharpe = orchestrator.compute_live_sharpe()
                drift = calibrator.check_sharpe_drift(
                    live_sharpe, backtest_sharpe=1.2, live_trades=trade_count,
                    killswitch=killswitch,
                )
                if drift["status"] in ("emergency_downsized", "de_risked"):
                    orchestrator.apply_sharpe_multiplier(drift["risk_multiplier"])
                    logger.warning(
                        f"Auto-de-risk: multiplier={drift['risk_multiplier']:.2f} "
                        f"live_sharpe={live_sharpe:.2f} drift={drift['drift']:.2f}"
                    )
                elif drift["status"] == "normal":
                    orchestrator.apply_sharpe_multiplier(drift["risk_multiplier"])
                last_sharpe_check = trade_count

            # Save market snapshot for dashboard — real 24h change, F&G, market cap
            if current_prices:
                _build_market_snapshot(live.exchange, current_prices)

            # Persist a portfolio snapshot every cycle — the dashboard's REAL
            # equity-history source (vs the in-memory 20-trade window). Total PnL
            # comes from the full journal, not the last-20 window.
            try:
                pf = paper.get_portfolio()
                total_pnl_row = store.conn.execute(
                    "SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE status='closed' AND pnl IS NOT NULL"
                ).fetchone()
                store.insert_portfolio_snapshot(
                    balance=pf.get("balance", 0),
                    equity=pf.get("equity", 0),
                    open_positions=pf.get("open_positions", 0),
                    daily_pnl=pf.get("daily_pnl", 0),
                    total_pnl=float(total_pnl_row[0] or 0) if total_pnl_row else 0.0,
                )
            except Exception as e:
                logger.debug(f"Portfolio snapshot skip: {e}")

            invalidate_dashboard()  # cycle done — refresh dashboard clients

            if state and trade_count > 0 and trade_count % 5 == 0:
                state.refresh_gate()

            time.sleep(max(0, cycle_seconds - len(coins) * 2))

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        watchdog.stop()
        store.close()
        logger.info("TradingBot stopped")


# Market data TTL cache — reuses data within cycle_seconds to avoid redundant API calls
_market_data_cache: dict[str, tuple[float, dict]] = {}
_market_data_cache_ttl: float = 30.0

# Web-data cache — Fear & Greed / market cap refresh sparingly (they change slowly)
_web_data_cache: dict[str, tuple[float, dict]] = {}
_web_data_cache_ttl: float = 300.0


def _build_market_snapshot(exchange, current_prices: dict) -> None:
    """Write a dashboard market snapshot with REAL data:
    - 24h change computed from actual 1d candles (not hardcoded)
    - Fear & Greed index from alternative.me (same source the bot validates against)
    - Total market cap / change from CoinGecko global endpoint
    Falls back gracefully to cached/demo values if a source is unreachable.
    """
    import json
    import time

    now = time.time()
    try:
        coins = []
        for sym, price in list(current_prices.items())[:10]:
            change_24h = 0.0
            try:
                candles_1d = exchange.fetch_ohlcv(sym, "1d", limit=2)
                if candles_1d and len(candles_1d) >= 2:
                    prev_close = candles_1d[-2][4]
                    last_close = candles_1d[-1][4]
                    if prev_close > 0:
                        change_24h = round((last_close - prev_close) / prev_close * 100, 2)
            except Exception:
                change_24h = 0.0
            coins.append({"symbol": sym, "price": round(float(price), 6), "change_24h": change_24h})

        total_cap = "2.42T"
        cap_chg = 0.0
        fng = 50
        fng_label = "NEUTRAL"

        # Fear & Greed from alternative.me (real web data)
        try:
            cached = _web_data_cache.get("fng")
            if cached and (now - cached[0]) < _web_data_cache_ttl:
                fng = cached[1]["fng"]
                fng_label = cached[1]["label"]
            else:
                resp = httpx.get("https://api.alternative.me/fng/?limit=1", timeout=8)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    if data:
                        fng = int(data[0]["value"])
                        fng_label = data[0].get("value_classification", "NEUTRAL").upper()
                        _web_data_cache["fng"] = (time.time(), {"fng": fng, "label": fng_label})
        except Exception:
            pass

        # Total market cap from CoinGecko global endpoint
        try:
            cached = _web_data_cache.get("cap")
            if cached and (now - cached[0]) < _web_data_cache_ttl:
                total_cap = cached[1]["cap"]
                cap_chg = cached[1]["chg"]
            else:
                resp = httpx.get(
                    "https://api.coingecko.com/api/v3/global", timeout=8,
                    headers={"User-Agent": "KairoTradingBot/1.0"},
                )
                if resp.status_code == 200:
                    g = resp.json().get("data", {})
                    cap_usd = (g.get("total_market_cap") or {}).get("usd", 0)
                    cap_chg = (g.get("market_cap_change_percentage_24h_usd") or 0)
                    if cap_usd > 0:
                        total_cap = f"${cap_usd/1e12:.2f}T"
                        _web_data_cache["cap"] = (time.time(), {"cap": total_cap, "chg": round(cap_chg, 2)})
        except Exception:
            pass

        snap = {
            "coins": coins,
            "total_market_cap": total_cap,
            "market_cap_change": cap_chg,
            "fear_greed_index": fng,
            "fear_greed_label": fng_label,
            "t": datetime.now().isoformat(),
        }
        Path("data/market_snapshot.json").write_text(json.dumps(snap))
    except Exception as e:
        logger.debug(f"Market snapshot skip: {e}")



_INFO_BAR_TYPE = "volume"   # volume | dollar | tick — set from settings in main()
_INFO_BARS_ENABLED = True


def _set_info_bar_config(enabled: bool, bar_type: str):
    global _INFO_BARS_ENABLED, _INFO_BAR_TYPE
    _INFO_BARS_ENABLED = enabled
    _INFO_BAR_TYPE = bar_type


def _build_market_data(exchange, symbol: str, store=None) -> dict:
    import numpy as np
    import time

    # TTL cache: return cached data if fresh
    now = time.time()
    cached = _market_data_cache.get(symbol)
    if cached and (now - cached[0]) < _market_data_cache_ttl:
        return cached[1]

    data = {}
    for tf in ["15m", "1h", "4h", "1d"]:
        try:
            candles = exchange.fetch_ohlcv(symbol, tf, limit=100)
            if not candles or len(candles) < 20:
                continue

            # P0.2: when enabled, the 15m block the strategies consume is
            # computed from info bars (volume bars by default) instead of
            # wall-clock time bars. Info bars sample on information arrival,
            # so the bursts that carry signal aren't blurred across dead hours.
            # 1h/4h/1d stay time-based; the info-bar block is also persisted.
            info_block_15m = None
            if tf == "15m" and _INFO_BARS_ENABLED:
                from src.pipeline.info_bars import build_info_bar_market_data, candles_to_info_bars
                try:
                    # Reuse the candles already fetched above — no extra API call.
                    info_block = build_info_bar_market_data(
                        exchange, symbol, bar_type=_INFO_BAR_TYPE, candles=candles)
                    if info_block:
                        info_block_15m = next(iter(info_block.values()))
                        data[f"{_INFO_BAR_TYPE}_bars"] = info_block_15m
                        if store is not None:
                            info = candles_to_info_bars(candles, _INFO_BAR_TYPE)
                            store.insert_info_bars(exchange.exchange_id, symbol, _INFO_BAR_TYPE, info)
                except Exception as e:
                    logger.debug(f"Info-bar block {symbol}: {e}")

            # Persist fresh candles so the dashboard chart / correlations stay live.
            # Only the forming bar + a couple of new ones change per cycle, so a
            # 4-candle tail keeps the upsert cost flat regardless of history.
            if store is not None:
                try:
                    store.insert_candles(exchange.exchange_id, symbol, tf, candles[-4:])
                except Exception:
                    pass

            last = candles[-1]
            closes = np.array([c[4] for c in candles], dtype=float)
            highs = np.array([c[2] for c in candles], dtype=float)
            lows = np.array([c[3] for c in candles], dtype=float)
            volumes = np.array([c[5] for c in candles], dtype=float)

            atr = float(np.mean(highs[-14:] - lows[-14:])) if len(candles) >= 14 else 0
            atr_pct = atr / last[4] if last[4] > 0 else 0.02

            sma20 = float(np.mean(closes[-20:])) if len(closes) >= 20 else last[4]
            sma50 = float(np.mean(closes[-50:])) if len(closes) >= 50 else last[4]
            vol_ratio = float(last[5] / np.mean(volumes[-20:])) if np.mean(volumes[-20:]) > 0 else 1.0

            deltas = np.diff(closes)
            gains = np.maximum(deltas, 0)
            losses = np.abs(np.minimum(deltas, 0))
            avg_gain = float(np.mean(gains[-14:]) if len(gains) >= 14 else 0)
            avg_loss = float(np.mean(losses[-14:]) if len(losses) >= 14 else 0)
            rsi_val = 100.0 - (100.0 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100.0

            std20 = float(np.std(closes[-20:])) if len(closes) >= 20 else 0
            bb_upper = sma20 + std20 * 2
            bb_lower = sma20 - std20 * 2

            vol_15m = abs((last[4] - closes[-2]) / closes[-2] * 100) if len(closes) >= 2 else 0

            ema12 = _calc_ema(closes, 12)
            ema26 = _calc_ema(closes, 26)
            macd = ema12 - ema26 if ema12 and ema26 else None
            macd_signal = _calc_ema(np.array([macd] if macd else []), 9) if macd else None
            adx_val = _calc_adx(highs, lows, closes, 14)

            data[tf] = {
                "open": float(last[1]), "high": float(last[2]),
                "low": float(last[3]), "close": float(last[4]),
                "volume": float(last[5]),
                "atr": round(atr, 6), "atr_pct": round(atr_pct, 4),
                "sma20": round(sma20, 6), "sma50": round(sma50, 6),
                "bb_upper": round(bb_upper, 6), "bb_lower": round(bb_lower, 6),
                "rsi": round(rsi_val, 1), "adx": round(adx_val, 1),
                "macd": round(macd, 6) if macd else None,
                "macd_signal": round(macd_signal, 6) if macd_signal else None,
                "volatility_15m": round(vol_15m, 2),
                "volume_ratio": round(vol_ratio, 2),
                "sma20_distance": round((last[4] - sma20) / std20, 2) if std20 > 0 else 0,
                "hour": float(datetime.utcnow().hour),  # UTC — must match meta-retrain hour
            }

            # P0.2: the info-bar block is the live 15m signal input when
            # enabled — strategies read data["15m"] for their fastest timeframe.
            if tf == "15m" and info_block_15m:
                data[tf] = dict(data[tf])
                data[tf].update({k: v for k, v in info_block_15m.items() if k in (
                    "close", "atr", "atr_pct", "sma20", "sma50", "bb_upper",
                    "bb_lower", "rsi", "adx", "macd", "macd_signal",
                    "volatility_15m", "volume_ratio", "sma20_distance", "hour",
                )})
        except Exception as e:
            logger.debug(f"Market data {symbol} {tf}: {e}")
    _market_data_cache[symbol] = (time.time(), data)
    return data


def _restore_trade_history(paper, store) -> int:
    """Reload closed trades from the persistent DB into the in-memory paper
    journal so the dashboard feed / strategy stats survive restarts."""
    try:
        rows = store.conn.execute(
            "SELECT id, symbol, side, entry_price, exit_price, quantity, entry_time, "
            "exit_time, exit_reason, strategy FROM trades WHERE status='closed' "
            "ORDER BY exit_time ASC"
        ).fetchall()
    except Exception:
        return 0
    restored = 0
    total_pnl = 0.0
    for r in rows:
        tid, sym, side, entry, exit_px, qty, entry_t, exit_t, reason, strategy = r
        if not entry or not exit_px or not qty:
            continue
        gross = (exit_px - entry) * qty
        if str(side) == "short":
            gross = -gross
        net = gross - exit_px * qty * paper.fee_pct * 2  # approx round-trip fee
        pnl_pct = net / (entry * qty) * 100  # same formula as paper.close_position
        paper.trade_log.append({
            "exchange": "paper", "symbol": sym, "side": side,
            "entry_price": entry, "exit_price": exit_px, "quantity": qty,
            "usdt_value": entry * qty, "entry_time": entry_t, "exit_time": exit_t,
            "pnl": net, "pnl_pct": pnl_pct,
            "status": "closed", "exit_reason": reason, "strategy": strategy,
        })
        # Backfill legacy rows where pnl was never persisted (pre-v1.0) so
        # /tax, FuturesGate, report and finetune see real closed trades.
        try:
            store.conn.execute(
                "UPDATE trades SET pnl=?, pnl_pct=? WHERE id=? AND pnl IS NULL",
                [net, pnl_pct, tid],
            )
        except Exception:
            pass
        total_pnl += net
        restored += 1
    if restored:
        paper.balance = max(paper.balance + total_pnl, 1.0)
        paper.equity = paper.balance
        logger.info(f"Restored {restored} closed trades into paper journal (net PnL ${total_pnl:.2f})")
    return restored


def _seed_paper_trades(paper, exchange, settings, count: int | None = None, store=None) -> int:
    """Seed the empty paper journal with a handful of realistic completed trades.

    Idempotent across restarts: skipped if the persistent trades table already
    has history. Uses REAL ticker prices from the exchange for the entry, then
    simulates a plausible round trip (win/loss mix across the bot's actual
    strategy names) so the dashboard feed, per-strategy stats and equity curve
    render real-looking data immediately.
    """
    import random
    from src.pipeline.historical import load_coins

    # Idempotency guard — the in-memory paper trader resets each boot, so check
    # the persistent DB instead of paper.get_portfolio().
    try:
        if store is not None:
            existing = store.conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            if existing > 0:
                logger.info(f"Trades table already has {existing} rows — skipping seed")
                return 0
    except Exception:
        pass

    if count is None:
        count = int(settings.get("seeding", {}).get("paper_trade_count", 14))
    coins = load_coins()[:6]
    # Real strategy names — the SignalEngine logs the strategy class __name__
    strategies = ["Breakout", "MovingAverageCross", "RSIMeanReversion", "BollingerReversion", "VolumeSpike"]
    rng = random.Random(42)
    seeded = 0
    for i in range(count):
        coin = rng.choice(coins)
        try:
            ticker = exchange.fetch_ticker(coin)
            if not ticker or not ticker.get("last"):
                continue
            price = float(ticker["last"])
            side = "long" if rng.random() > 0.4 else "short"
            entry = price * (1 + rng.uniform(-0.004, 0.004))
            move = rng.uniform(-1.3, 2.6)  # realistic % move for the round trip
            exit_price = entry * (1 + move / 100) if side == "long" else entry * (1 - move / 100)
            qty = 0.001 if "BTC" in coin else (0.4 if "ETH" in coin else 25)
            strategy = strategies[i % len(strategies)]
            trade = paper.open_position(coin, side, entry, qty, entry * 0.97, entry * 1.05, strategy=strategy)
            if not trade:
                continue
            reason = "take_profit" if move > 0.2 else "stop_loss"
            paper.close_position(trade, exit_price, reason)
            seeded += 1
        except Exception as e:
            logger.debug(f"Seed trade {coin} skipped: {e}")
    if seeded:
        logger.info(f"Seeded {seeded} paper trades to populate the dashboard feed")
    return seeded


def _calc_ema(prices: np.ndarray, period: int) -> float | None:
    if len(prices) < period:
        return None
    alpha = 2 / (period + 1)
    ema = prices[0]
    for i in range(1, len(prices)):
        ema = alpha * prices[i] + (1 - alpha) * ema
    return float(ema)


def _calc_adx(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    if len(highs) < period + 1:
        return 20.0
    high = highs[-period-1:]
    low = lows[-period-1:]
    close = closes[-period-1:]
    prev_close = np.roll(close, 1)

    tr = np.maximum(high - low, np.maximum(abs(high - prev_close), abs(low - prev_close)))[1:]
    atr = np.mean(tr[-period:]) if len(tr) >= period else 1.0
    if atr == 0:
        return 20.0

    up_move = high[1:] - high[:-1]
    down_move = low[:-1] - low[1:]

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    plus_di = 100 * np.mean(plus_dm[-period:]) / atr if np.mean(plus_dm[-period:]) else 0
    minus_di = 100 * np.mean(minus_dm[-period:]) / atr if np.mean(minus_dm[-period:]) else 0

    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
    return float(dx)


def _record_learning(scorecard, decision, trade):
    try:
        predicted = decision.get("action", "").lower()
        if predicted not in ("long", "short"):
            return
        trade_pnl = trade.get("pnl")
        if trade_pnl is None:
            return
        for agent_name in ["analyst", "strategist"]:
            scorecard.record(
                trade_id=str(trade.get("id", "unknown")),
                agent=agent_name, predicted=predicted,
                actual="long" if trade_pnl > 0 else "short",
                confidence=decision.get("confidence", 0.5),
            )
    except Exception as e:
        logger.debug(f"Scorecard skip: {e}")


def run_backtest_sweep(store, settings):
    logger.info("Running backtest sweep...")
    from src.backtest.engine import BacktestEngine
    from src.backtest.strategies.ma_cross import MovingAverageCross
    from src.backtest.strategies.rsi_meanrev import RSIMeanReversion
    from src.backtest.strategies.breakout import Breakout
    from src.backtest.strategies.bollinger_revert import BollingerReversion
    from src.backtest.strategies.volume_spike import VolumeSpike
    from src.pipeline.historical import load_coins

    engine = BacktestEngine(store, initial_cash=5000.0)
    coins = load_coins()[:5]
    strategies = [MovingAverageCross, RSIMeanReversion, Breakout, BollingerReversion, VolumeSpike]

    for sym in coins:
        for strat in strategies:
            result = engine.run(strat, sym, "bybit", "15m",
                              start_date="2024-01-01")
            if "metrics" in result:
                m = result["metrics"]
                logger.info(f"{sym} {strat.__name__}: Return={m['total_return_pct']}% "
                          f"Sharpe={m['sharpe_ratio']} WinRate={m['win_rate_pct']}% Trades={m['total_trades']}")

    store.close()
    logger.info("Backtest sweep complete")


def _backup_db(store=None):
    """Snapshot the DuckDB database — cheap insurance against corruption/crashes.

    The .db file is locked by the open connection on Windows, so a plain file
    copy fails. Uses DuckDB's ATTACH + COPY FROM DATABASE (verified on DuckDB
    1.1), which reads committed state through the live connection itself.
    """
    from pathlib import Path

    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / f"market_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ddb"

    if store is not None:
        try:
            current_db = store.conn.execute("SELECT current_database()").fetchone()[0]
            store.conn.execute(f"ATTACH '{dest.as_posix()}' AS backup_db (TYPE duckdb)")
            store.conn.execute(f"COPY FROM DATABASE {current_db} TO backup_db")
            store.conn.execute("DETACH backup_db")
            logger.info(f"DB backed up -> {dest}")
            return
        except Exception as e:
            logger.warning(f"DuckDB COPY backup failed ({e}) — falling back to file copy")

    src = Path("data/market.db")
    if not src.exists():
        return
    try:
        import shutil
        shutil.copy2(src, dest)
        logger.info(f"DB backed up (copy) -> {dest}")
    except Exception as e:
        logger.warning(f"DB backup failed: {e}")


def run_fng_validation(store, settings):
    logger.info("Validating Fear & Greed predictive value...")
    import numpy as np
    import httpx
    from datetime import datetime, timedelta

    try:
        resp = httpx.get("https://api.alternative.me/fng/?limit=365", timeout=20)
        if resp.status_code != 200:
            logger.warning("F&G API unavailable, skipping validation")
            return
        data = resp.json().get("data", [])
        if len(data) < 30:
            logger.warning(f"Only {len(data)} F&G data points — need 30+, skipping")
            return

        rows = store.conn.execute(
            "SELECT timestamp, close FROM candles WHERE symbol='BTC/USDT' AND timeframe='1d' ORDER BY timestamp ASC"
        ).fetchall()
        if len(rows) < 30:
            logger.warning("Not enough daily BTC data for F&G validation")
            return

        prices_by_date = {}
        for ts, close in rows:
            dt = datetime.fromtimestamp(ts / 1000).strftime("%d-%m-%Y")
            prices_by_date[dt] = float(close)

        fng_values = []
        forward_returns = []
        for entry in data:
            try:
                fng_dt = datetime.fromtimestamp(int(entry["timestamp"]))
                target_dt = fng_dt + timedelta(days=5)
                target_key = target_dt.strftime("%d-%m-%Y")
                current_key = fng_dt.strftime("%d-%m-%Y")
            except (ValueError, OSError):
                continue

            current_close = prices_by_date.get(current_key)
            target_close = prices_by_date.get(target_key)
            if not current_close or not target_close:
                continue

            fng_values.append(float(entry["value"]))
            forward_returns.append((target_close - current_close) / current_close)

        if len(fng_values) < 30:
            logger.warning(f"Only {len(fng_values)} aligned F&G/BTC points — need 30+")
            return

        from src.agents.sentiment import SentimentAgent
        agent = SentimentAgent()
        result = agent.validate_fear_greed(np.array(fng_values), np.array(forward_returns))
        logger.info(f"F&G validation: predictive={result['predictive']}, IC={result['ic']:.4f}, p={result['p_value']:.4f}")
    except Exception as e:
        logger.warning(f"F&G validation failed: {e}")


def _start_api_server(store, paper, orchestrator, killswitch, state=None, futures_trader=None,
                      market_maker=None, tri_arb=None, paper_mode: bool = True):
    """Start FastAPI server in a background thread for CommandCode/OpenCode integration."""
    from src.api.server import create_app
    import uvicorn

    app = create_app(store, paper, orchestrator, killswitch, state=state, futures_trader=futures_trader,
                     market_maker=market_maker, tri_arb=tri_arb, paper_mode=paper_mode)

    def run_api():
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    logger.info("API — http://127.0.0.1:8000")


def _execute_futures(futures_trader, decision: dict) -> dict | None:
    """Route a trade decision through the futures execution layer."""
    trade = decision.get("trade", decision)
    symbol = trade.get("symbol", "")
    action = trade.get("action", decision.get("action", ""))
    size_usdt = trade.get("usdt_value", trade.get("size_usdt", 0))
    entry_price = trade.get("entry_price", 0)
    stop_loss = trade.get("stop_loss", 0)
    take_profit = trade.get("take_profit", 0)

    if size_usdt <= 0 or entry_price <= 0:
        return None

    quantity = size_usdt / entry_price
    side = "buy" if action == "LONG" else "sell"

    result = futures_trader.open_position(
        symbol=symbol,
        side=side,
        amount=quantity,
        stop_loss=stop_loss if stop_loss > 0 else None,
        take_profit=take_profit if take_profit > 0 else None,
    )
    if result:
        result["usdt_value"] = size_usdt
        result["strategy"] = decision.get("strategy", "agent")
    return result


if __name__ == "__main__":
    main()
