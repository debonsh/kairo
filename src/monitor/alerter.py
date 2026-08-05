"""Multi-channel alerting — Slack webhook + enhanced Telegram alerts.
Sends critical alerts (stall, error, circuit-breaker, daily summary)."""

import os
import json
import asyncio
from loguru import logger
import httpx
import nest_asyncio
nest_asyncio.apply()


class Alerter:
    """Unified alert dispatcher: Slack + Telegram + log."""

    def __init__(self, telegram_bot=None):
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
        self.telegram = telegram_bot

    def is_configured(self) -> bool:
        return bool(self.slack_webhook_url) or bool(
            self.telegram and self.telegram.token
        )

    def alert(self, title: str, message: str, severity: str = "info"):
        """Fire-and-forget alert to all configured channels."""
        logger.info(f"[ALERT:{severity}] {title} — {message}")

        if self.slack_webhook_url:
            try:
                asyncio.run(self._send_slack(title, message, severity))
            except Exception as e:
                logger.warning(f"Slack alert failed: {e}")

        if self.telegram:
            try:
                emoji = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}
                tag = emoji.get(severity, "ℹ️")
                asyncio.run(
                    self.telegram.send_message(f"{tag} *{title}*\n{message}")
                )
            except Exception as e:
                logger.warning(f"Telegram alert failed: {e}")

    async def _send_slack(self, title: str, message: str, severity: str):
        color_map = {"critical": "danger", "warning": "warning", "info": "good"}
        color = color_map.get(severity, "good")
        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": title,
                    "text": message[:4000],
                    "footer": f"Kairo • {severity.upper()}",
                    "ts": int(asyncio.get_event_loop().time()),
                }
            ]
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self.slack_webhook_url, json=payload
            )
            if resp.status_code != 200:
                logger.warning(f"Slack webhook returned {resp.status_code}")

    def alert_stall(self, elapsed_seconds: float, kind: str):
        self.alert(
            f"STALL DETECTED — {kind}",
            f"{kind} has been silent for {elapsed_seconds:.0f}s. Check logs.",
            severity="critical",
        )

    def alert_api_error(self, consecutive_errors: int):
        self.alert(
            "API ERROR THRESHOLD",
            f"{consecutive_errors} consecutive exchange API errors — "
            f"trading auto-paused.",
            severity="critical",
        )

    def alert_sharpe_drift(self, live_sharpe: float, backtest_sharpe: float):
        self.alert(
            "SHARPE DRIFT",
            f"Live Sharpe {live_sharpe:.2f} vs backtest {backtest_sharpe:.2f}. "
            f"Risk multiplier auto-adjusted.",
            severity="warning",
        )

    def alert_startup(self):
        self.alert("Kairo Online", "Bot started successfully.", severity="info")

    def alert_daily_summary(self, summary_text: str):
        self.alert("Daily Summary", summary_text, severity="info")