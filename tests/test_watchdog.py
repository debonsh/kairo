"""Tests for FastWatchdog — the stall detector behind Telegram alerts.

Regression for the false "STALL DETECTED — websocket" alarms: when the bot
is paused/stopped the loop is intentionally idle, so no stall should fire.
Also locks in alert-once-per-episode + recovery notices.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.monitor.fast_watchdog import FastWatchdog


class FakeKillswitch:
    def __init__(self, allowed: bool = True):
        self.allowed = allowed

    def trading_allowed(self) -> bool:
        return self.allowed


class FakeAlerter:
    """Records alerts instead of sending them."""

    def __init__(self):
        self.alerts = []

    def alert_stall(self, elapsed_seconds: float, kind: str):
        self.alerts.append(("stall", kind, elapsed_seconds))

    def alert(self, title: str, message: str, severity: str = "info"):
        self.alerts.append((severity, title, message))


def _make_watchdog(allowed: bool = True, threshold: int = 600) -> FastWatchdog:
    ks = FakeKillswitch(allowed=allowed)
    alerter = FakeAlerter()
    wd = FastWatchdog(stall_threshold_seconds=threshold, alerter=alerter,
                      killswitch=ks)
    # Make the watchdog look like it has been silent well past the threshold.
    wd.last_cycle_time = time.time() - threshold - 60
    wd.last_price_ping = time.time() - threshold - 60
    return wd, alerter, ks


def test_paused_bot_never_alerts():
    """A paused bot is intentionally idle — silence is not a stall."""
    wd, alerter, _ = _make_watchdog(allowed=False)
    wd._check_once()
    assert alerter.alerts == [], f"Paused bot must not alert, got {alerter.alerts}"
    # Timers re-armed so resume starts clean.
    assert time.time() - wd.last_cycle_time < 5
    assert time.time() - wd.last_price_ping < 5


def test_stall_alerts_once_per_episode():
    """Repeated silence must alert once, not spam every 30s tick."""
    wd, alerter, _ = _make_watchdog(allowed=True)

    wd._check_once()
    wd._check_once()  # same episode, still silent
    kinds = [a for a in alerter.alerts if a[0] == "stall"]
    assert len(kinds) == 2, f"Expected one alert per stream, got {kinds}"
    assert {k[1] for k in kinds} == {"main loop", "price stream"}
    assert wd.stall_count == 2


def test_recovery_after_stall():
    """A fresh ping after a stall sends a recovery notice and re-arms."""
    wd, alerter, _ = _make_watchdog(allowed=True)
    wd._check_once()
    assert wd.stall_count == 2

    wd.ping_price_stream()
    recovered = [a for a in alerter.alerts if a[1] == "RECOVERED — price stream"]
    assert len(recovered) == 1, f"Expected a price-stream recovery, got {alerter.alerts}"
    assert wd.recovery_count == 1

    # Same stream now stalls again -> a NEW alert fires (episode ended).
    wd.last_price_ping = time.time() - wd.threshold - 60
    wd._check_once()
    stalls = [a for a in alerter.alerts if a[0] == "stall"]
    assert len(stalls) == 3, f"Expected 3rd stall alert, got {stalls}"


def test_resume_after_pause_no_false_alarm():
    """Pause re-arms timers, so resuming cannot fire an instant stall."""
    wd, alerter, ks = _make_watchdog(allowed=False)
    wd._check_once()  # idle: re-arms timers, no alert

    ks.allowed = True  # user resumes
    wd._check_once()   # fresh timers -> must not alert
    assert alerter.alerts == [], f"Resume must not alert, got {alerter.alerts}"


def test_status_healthy_while_idle():
    """Paused bot reports healthy — it is alive, just not trading."""
    wd, _, _ = _make_watchdog(allowed=False)
    status = wd.get_status()
    assert status["healthy"] is True
    assert status["stall_count"] == 0


def test_stall_flag_survives_pause_for_recovery():
    """A real stall paused over still fires its recovery notice on resume."""
    wd, alerter, ks = _make_watchdog(allowed=True)
    wd._check_once()  # real stall fires -> flags set
    assert wd.stall_count == 2

    ks.allowed = False
    wd._check_once()  # pause: re-arms timers, keeps flags, no alert
    assert alerter.alerts and all(a[0] == "stall" for a in alerter.alerts)

    ks.allowed = True
    wd.ping_price_stream()  # resume ping -> recovery notice for the stall
    recovered = [a for a in alerter.alerts if a[1] == "RECOVERED — price stream"]
    assert len(recovered) == 1, f"Expected recovery on resume, got {alerter.alerts}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL WATCHDOG TESTS PASSED")
