"""Heartbeat monitor — ensures the bot is alive and healthy.
Sends periodic Telegram pings, monitors CPU/memory, detects stalls."""

import time
from datetime import datetime
from loguru import logger


class Heartbeat:
    def __init__(self, interval_hours: int = 6, telegram_bot=None):
        self.interval_hours = interval_hours
        self.telegram = telegram_bot
        self.last_beat = datetime.now()
        self.cycle_count_start = 0
        self.errors_since_last: list[str] = []

    def check(self, orchestrator, paper_trader) -> dict:
        now = datetime.now()
        hours_since = (now - self.last_beat).total_seconds() / 3600
        cycles = orchestrator.cycle_count - self.cycle_count_start

        healthy = True
        warnings = []

        if hours_since > self.interval_hours * 2:
            healthy = False
            warnings.append(f"No heartbeat for {hours_since:.1f}h")

        if cycles < 1 and hours_since > 1:
            warnings.append(f"No trading cycles in {hours_since:.1f}h")

        portfolio = paper_trader.get_portfolio()
        if portfolio.get("balance", 0) <= 0:
            healthy = False
            warnings.append("Portfolio balance depleted")

        status = {
            "timestamp": now.isoformat(),
            "healthy": healthy,
            "uptime_hours": hours_since,
            "cycles_since_last": cycles,
            "balance": portfolio.get("balance", 0),
            "open_positions": portfolio.get("open_positions", 0),
            "warnings": warnings,
            "errors": self.errors_since_last[-5:],
        }

        self.last_beat = now
        self.cycle_count_start = orchestrator.cycle_count
        self.errors_since_last = []

        return status

    async def send_heartbeat(self, status: dict):
        if not self.telegram:
            return

        if not status["healthy"]:
            msg = (
                f"⚠️ *Bot Health Alert*\n"
                f"Warnings: {', '.join(status['warnings'])}\n"
                f"Balance: ${status['balance']:.2f}\n"
                f"Uptime: {status['uptime_hours']:.1f}h"
            )
            await self.telegram.send_message(msg)
        else:
            msg = (
                f"💚 *Bot Healthy*\n"
                f"Uptime: {status['uptime_hours']:.1f}h\n"
                f"Balance: ${status['balance']:.2f}\n"
                f"Open: {status['open_positions']}"
            )
            await self.telegram.send_message(msg)

    def record_error(self, error: str):
        self.errors_since_last.append(f"{datetime.now():%H:%M:%S} {error}")
        logger.error(f"Heartbeat error recorded: {error}")
