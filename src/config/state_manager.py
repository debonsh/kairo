"""RuntimeStateManager — hot-swappable mode profiles (vanilla | aggressive).

Single source of truth for which parameter profile the trading pipeline uses
RIGHT NOW. The active mode is persisted to ``data/runtime_state.json`` so the
bot process, Telegram command handlers, and the Streamlit dashboard (a
separate process) all share it with ZERO restarts:

  - ``set_mode()`` from Telegram (/mode, /aggressive, /vanilla) or the
    dashboard toggle → atomic file write → picked up on the next tick.
  - ``get_active_params()`` deep-merges ``config/risk_rules.yaml`` base rules
    with the active profile. Pure in-memory, no I/O per call, safe to invoke
    on every evaluation tick without blocking the trading loop.
  - Thread-safe via ``threading.RLock`` (Telegram thread + trading loop).

Futures integration (v0.3):
  - Bridges FuturesGate + FuturesTrader for leverage scaling.
  - When mode switches to 'vanilla': leverage forced to 1x, futures routing off.
  - When mode switches to 'aggressive': checks FuturesGate, sets leverage if unlocked.
"""

import json
import os
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import yaml
from loguru import logger

VALID_MODES = ("vanilla", "aggressive")
STATE_FILE = Path("data/runtime_state.json")


def micro_capital_effective_pct(balance: float, base_pct: float, params: dict,
                                min_order_usdt: float | None = None) -> float:
    """Effective max position % for the given account balance.

    Micro accounts (balance < micro_capital.balance_threshold) get a scaled-up
    effective % so a single order clears the ACTUAL exchange minimum (max of
    ``min_meaningful_order_usdt`` and the symbol's ``min_order_usdt``) — while
    USD risk stays bounded by the sizing engine and ``max_position_pct``
    ceiling. Shared by the RiskManager (sizing caps) and the Gate (final
    position check) so both layers stay consistent.
    """
    micro = params.get("micro_capital") or {}
    if not micro.get("enabled", True):
        return base_pct
    threshold = float(micro.get("balance_threshold", 2000))
    if balance >= threshold:
        return base_pct
    min_meaningful = float(micro.get("min_meaningful_order_usdt", 5.0))
    if min_order_usdt:
        min_meaningful = max(min_meaningful, min_order_usdt)
    ceiling = float(micro.get("max_position_pct", 20.0))
    required_pct = min_meaningful / balance * 100 if balance > 0 else base_pct
    return min(max(base_pct, required_pct), ceiling)


def conviction_multiplier(p: float | None, params: dict) -> float:
    """Meta-confidence scaling factor — size grows with statistical conviction.

    conv = 1 + conviction_scale · (p − floor)/(1 − floor), capped at
    conviction_max_mult. p is the meta-labeler probability of a profitable
    trade; at the floor (0.55) conv = 1.0, at p = 1.0 conv = 1 + scale.
    Returns 1.0 (no scaling) when the meta-labeler is untrained (p is None)
    or conviction_scale is 0 (vanilla default).
    """
    sizing = params.get("sizing") or {}
    scale = float(sizing.get("conviction_scale", 0.0))
    if scale <= 0 or p is None:
        return 1.0
    floor = float(sizing.get("meta_min_probability", 0.55))
    max_mult = float(sizing.get("conviction_max_mult", 1.5))
    p = min(max(float(p), 0.0), 1.0)
    span = 1.0 - floor
    if span <= 0:
        return 1.0
    conv = 1.0 + scale * ((p - floor) / span)
    return min(conv, max_mult)


def effective_position_pct(balance: float, base_pct: float, params: dict,
                           regime: str = "unknown", meta_p: float | None = None,
                           min_order_usdt: float | None = None) -> float:
    """The per-trade position % the Gate enforces and the RiskManager sizes to.

    Combines all three scaling levers into one number:
      base = micro_capital_effective_pct(balance, base_pct)   (micro scale-up)
      conv = conviction_multiplier(meta_p, params)            (meta-confidence)
      M    = regime_multipliers[regime]                       (press winners)
    Returns base · conv · max(M, 1).

    Shared by RiskManager and Gate so both layers agree exactly.
    """
    base = micro_capital_effective_pct(balance, base_pct, params, min_order_usdt)
    conv = conviction_multiplier(meta_p, params)
    m_regime = float((params.get("regime_multipliers") or {}).get(regime, 1.0))
    return base * conv * max(m_regime, 1.0)


def get_dedup_key(market_data: dict) -> str:
    """Deterministic hash of market data — used to detect identical data frames
    across consecutive cycles and skip redundant LLM calls."""
    import hashlib
    parts = []
    for tf in ["15m", "1h", "4h", "1d"]:
        d = market_data.get(tf, {})
        if isinstance(d, dict):
            parts.append(str(d.get("close", "")))
            parts.append(str(d.get("atr", "")))
            parts.append(str(d.get("rsi", "")))
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:12]


def deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


class RuntimeStateManager:
    """Thread-safe runtime mode/profile manager persisted to JSON."""

    def __init__(self, state_path: str | Path = "data/runtime_state.json",
                 rules_path: str | Path = "config/risk_rules.yaml"):
        self._lock = threading.RLock()
        self._state_path = Path(state_path)
        self._rules_path = Path(rules_path)
        self._mode = "vanilla"
        self._rules: dict = {}
        self._subscribers: list = []
        self._poller_running = False

        self._load_state()
        self._load_rules()

    def _load_state(self):
        try:
            if self._state_path.exists():
                with open(self._state_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                mode = data.get("mode", "vanilla")
                if mode in VALID_MODES:
                    self._mode = mode
        except Exception as exc:
            logger.warning(f"Runtime state read failed ({exc}) — using vanilla")

    def _save_state(self):
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "mode": self._mode,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            tmp = self._state_path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            os.replace(tmp, self._state_path)
        except Exception as exc:
            logger.warning(f"Runtime state write failed ({exc})")

    def _load_rules(self):
        try:
            if self._rules_path.exists():
                with open(self._rules_path, "r", encoding="utf-8") as fh:
                    self._rules = yaml.safe_load(fh) or {}
        except Exception as exc:
            logger.warning(f"risk_rules.yaml load failed ({exc}) — using empty rules")

    def get_mode(self) -> str:
        with self._lock:
            return self._mode

    def set_mode(self, mode: str) -> bool:
        with self._lock:
            mode = (mode or "").strip().lower()
            if mode not in VALID_MODES:
                logger.warning(f"Invalid mode '{mode}' — must be one of {VALID_MODES}")
                return False
            if mode == self._mode:
                return True
            old_mode = self._mode
            self._mode = mode
            self._load_rules()
            self._save_state()

        logger.info(f"Runtime mode switched -> {mode} (was {old_mode})")
        for callback in list(self._subscribers):
            try:
                callback(mode)
            except Exception as exc:
                logger.debug(f"Mode subscriber failed: {exc}")
        return True

    def start(self, poll_interval: float = 2.0) -> None:
        """Start a daemon poller that syncs mode changes made by OTHER processes
        (e.g. the Streamlit dashboard) into this instance. Idempotent — safe to
        call from both the bot and the dashboard. The poller thread does the
        only file I/O, so the trading loop stays non-blocking.
        """
        with self._lock:
            if self._poller_running:
                return
            self._poller_running = True
        threading.Thread(target=self._poll_loop, args=(poll_interval,), daemon=True).start()

    def _poll_loop(self, interval: float):
        while True:
            time.sleep(interval)
            self._sync_from_disk()

    def _sync_from_disk(self):
        """Reload mode if another process changed the state file (last-writer-wins)."""
        try:
            if not self._state_path.exists():
                return
            with open(self._state_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            disk_mode = data.get("mode", "vanilla")
            if disk_mode not in VALID_MODES:
                return
            with self._lock:
                if disk_mode == self._mode:
                    return
                self._mode = disk_mode
                self._load_rules()  # profile edits are picked up too
            logger.info(f"Runtime mode synced from state file -> {disk_mode}")
            for callback in list(self._subscribers):
                try:
                    callback(disk_mode)
                except Exception as exc:
                    logger.debug(f"Mode subscriber failed: {exc}")
        except Exception:
            pass  # transient file state (mid-write) — try again next poll

    def subscribe(self, callback) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def get_active_params(self) -> dict:
        with self._lock:
            base = {k: v for k, v in self._rules.items() if k != "profiles"}
            profile = (self._rules.get("profiles") or {}).get(self._mode) or {}
            merged = deep_merge(base, profile)
            merged["mode"] = self._mode
            return merged

    def get_profile(self) -> dict:
        with self._lock:
            return (self._rules.get("profiles") or {}).get(self._mode) or {}

    def status(self) -> dict:
        params = self.get_active_params()
        pre_trade = params.get("pre_trade", {})
        sizing = params.get("sizing", {})
        return {
            "mode": self._mode,
            "max_position_pct": pre_trade.get("max_position_pct", 2.0),
            "min_confidence": pre_trade.get("min_confidence", 0.55),
            "kelly_fraction": sizing.get("kelly_fraction", 0.25),
            "vol_target_risk_pct": sizing.get("vol_target_risk_pct", 0.01),
            "sl_atr_multiplier": sizing.get("sl_atr_multiplier", 2.0),
            "tp_atr_multiplier": sizing.get("tp_atr_multiplier", 4.0),
            "min_risk_reward_ratio": pre_trade.get("min_risk_reward_ratio", 1.5),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


class StateManager(RuntimeStateManager):
    """Futures-aware state manager — bridges FuturesGate + FuturesTrader.

    Extends RuntimeStateManager with:
    - Leverage scaling: vanilla → 1x, aggressive → up to 2x (if gate unlocked)
    - FuturesGate integration for gate checking on mode switch
    - FuturesTrader integration for automatic leverage propagation
    """

    def __init__(self, futures_gate=None, futures_trader=None,
                 state_path: str | Path = "data/runtime_state.json",
                 rules_path: str | Path = "config/risk_rules.yaml"):
        super().__init__(state_path=state_path, rules_path=rules_path)
        self.gate = futures_gate
        self.futures = futures_trader
        self._futures_unlocked = False
        self._leverage = 1.0

    def set_mode(self, mode: str) -> dict:
        """Switch mode + auto-scale leverage.

        Returns dict with mode change details for API responses.
        """
        old_mode = self._mode
        old_leverage = self._leverage

        result = super().set_mode(mode)

        if self.gate and hasattr(self.gate, "set_mode"):
            self.gate.set_mode(mode)

        if mode == "vanilla":
            self._futures_unlocked = False
            self._leverage = 1.0
        elif mode == "aggressive":
            self._refresh_gate_inner()

        if self.futures and hasattr(self.futures, "leverage"):
            self.futures.leverage = self._leverage

        return {
            "mode": self._mode,
            "leverage": self._leverage,
            "futures_unlocked": self._futures_unlocked,
            "previous_mode": old_mode,
            "previous_leverage": old_leverage,
            "success": result,
        }

    def _refresh_gate_inner(self):
        if self.gate is None or self._mode != "aggressive":
            return
        if hasattr(self.gate, "evaluate"):
            try:
                g = self.gate.evaluate()
                self._futures_unlocked = g.unlocked
                self._leverage = g.allowed_leverage
            except Exception:
                self._futures_unlocked = False
                self._leverage = 1.0

    def refresh_gate(self):
        prev = self._futures_unlocked
        self._refresh_gate_inner()

        if self.futures and hasattr(self.futures, "leverage"):
            self.futures.leverage = self._leverage

        if prev != self._futures_unlocked:
            logger.info(
                f"Futures gate changed: unlocked={prev} → {self._futures_unlocked} "
                f"| leverage={self._leverage}x"
            )

    def should_use_futures(self, action: str = "LONG") -> bool:
        return self._mode == "aggressive" and self._futures_unlocked and self._leverage > 1.0

    @property
    def leverage(self) -> float:
        return self._leverage

    @property
    def futures_unlocked(self) -> bool:
        return self._futures_unlocked

    def get_status(self) -> dict:
        return {
            "mode": self._mode,
            "leverage": self._leverage,
            "futures_unlocked": self._futures_unlocked,
            "execution_path": "futures" if self.should_use_futures() else "spot",
        }
