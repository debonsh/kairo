"""Fast Watchdog — stall detection at 30-second intervals.
Separate from the 6-hour heartbeat. If the main loop stalls, you
get a Telegram alert in 3 minutes, not 6 hours.

The watchdog is killswitch-aware: while trading is paused or stopped the
loop is *intentionally* idle, so stall alerts are suppressed (and the
timers re-armed so a resume never fires an instant false alarm). Note that
a hang while paused is undetectable by design — pause is indistinguishable
from idle; the 6h heartbeat + healthchecks.io dead-man's switch cover that.

"price stream" = live ticker data flow. Live mode polls REST tickers each
cycle — the ccxt.pro LiveStream (src/pipeline/websocket.py) is not used in
production, so "websocket" was a misleading stall kind.

Stall alerts fire once per episode (not every 30s), and a recovery notice
is sent when the stream comes back.

ponytail: simple loop counter check, no complex state machine.
"""

import time
import threading
from loguru import logger


class FastWatchdog:
    def __init__(self, stall_threshold_seconds: int = 180, telegram_bot=None,
                 alerter=None, killswitch=None):
        self.threshold = stall_threshold_seconds
        self.telegram = telegram_bot
        self.alerter = alerter
        self.killswitch = killswitch
        self.last_cycle_time = time.time()
        self.last_price_ping = time.time()
        self._running = False
        self._thread: threading.Thread | None = None
        self.stall_count = 0
        self.recovery_count = 0
        self._cycle_stalled = False
        self._price_stalled = False
        self._lock = threading.Lock()

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"Watchdog started (threshold: {self.threshold}s)")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def ping_cycle(self):
        with self._lock:
            self.last_cycle_time = time.time()
            was_stalled = self._cycle_stalled
            self._cycle_stalled = False
        if was_stalled:
            self._notify_recovery("main loop")

    def ping_price_stream(self):
        with self._lock:
            self.last_price_ping = time.time()
            was_stalled = self._price_stalled
            self._price_stalled = False
        if was_stalled:
            self._notify_recovery("price stream")

    def _is_intentionally_idle(self) -> bool:
        return bool(self.killswitch and not self.killswitch.trading_allowed())

    def _loop(self):
        while self._running:
            time.sleep(30)
            self._check_once()

    def _check_once(self):
        """One watchdog tick — extracted for deterministic testing."""
        if self._is_intentionally_idle():
            # Paused/stopped — no data flow is expected, so an idle loop is
            # NOT a stall. Re-arm the timers so resume starts clean. Stall
            # flags are left intact: if a real stall was in progress, the
            # first ping after resume fires the recovery notice.
            with self._lock:
                self.last_cycle_time = time.time()
                self.last_price_ping = time.time()
            return

        with self._lock:
            cycle_elapsed = time.time() - self.last_cycle_time
            price_elapsed = time.time() - self.last_price_ping

        if cycle_elapsed > self.threshold:
            self._on_stall(cycle_elapsed, "main loop")
        if price_elapsed > self.threshold:
            self._on_stall(price_elapsed, "price stream")

    def _on_stall(self, elapsed: float, kind: str):
        """Fire exactly one critical alert per stall episode — never spam."""
        flag = "_cycle_stalled" if kind == "main loop" else "_price_stalled"
        ts_attr = "last_cycle_time" if kind == "main loop" else "last_price_ping"
        with self._lock:
            if getattr(self, flag):
                logger.debug(f"Watchdog: {kind} still silent ({elapsed:.0f}s) — no repeat alert")
                return
            # Re-verify freshness under the lock — a ping may have landed
            # between the elapsed read in _check_once and this call.
            if time.time() - getattr(self, ts_attr) <= self.threshold:
                return
            setattr(self, flag, True)
            self.stall_count += 1

        msg = f"⚠️ STALL DETECTED: {kind} silent for {elapsed:.0f}s (threshold: {self.threshold}s)"
        logger.critical(msg)

        if self.alerter:
            self.alerter.alert_stall(elapsed, kind)
        elif self.telegram:
            self._send_telegram(msg)

    def _notify_recovery(self, kind: str):
        with self._lock:
            self.recovery_count += 1
        msg = f"✅ {kind} recovered — data flow resumed"
        logger.info(msg)
        if self.alerter:
            try:
                self.alerter.alert(f"RECOVERED — {kind}", f"{kind} resumed after a stall.", severity="info")
            except Exception as e:
                logger.debug(f"Recovery alert failed: {e}")
        elif self.telegram:
            self._send_telegram(msg)

    def _send_telegram(self, msg: str):
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.telegram.send_message(msg))
            loop.close()
        except Exception as e:
            logger.error(f"Watchdog failed to send Telegram: {e}")

    def get_status(self) -> dict:
        with self._lock:
            now = time.time()
            idle = self._is_intentionally_idle()
            return {
                "last_cycle_seconds_ago": round(now - self.last_cycle_time, 1),
                "last_price_seconds_ago": round(now - self.last_price_ping, 1),
                "stall_count": self.stall_count,
                "recovery_count": self.recovery_count,
                "healthy": idle or (now - self.last_cycle_time) < self.threshold,
            }
