"""Telegram Bot — alerts, commands, and kill switch.
Runs in a daemon thread for async polling without blocking the main loop."""

import os
import sys
import asyncio
import threading
from loguru import logger

import nest_asyncio
nest_asyncio.apply()

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


class TelegramBot:
    def __init__(self, killswitch, paper_trader=None, state_manager=None):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.killswitch = killswitch
        self.paper = paper_trader
        self.state = state_manager
        self.app: Application | None = None
        self._initialized = False

    def run_sync(self):
        if not self.token:
            logger.warning("Telegram token not set — bot disabled")
            return

        self.app = Application.builder().token(self.token).build()
        self.app.add_handler(CommandHandler("stop", self._handle_stop))
        self.app.add_handler(CommandHandler("pause", self._handle_pause))
        self.app.add_handler(CommandHandler("resume", self._handle_resume))
        self.app.add_handler(CommandHandler("status", self._handle_status))
        self.app.add_handler(CommandHandler("positions", self._handle_positions))
        self.app.add_handler(CommandHandler("pnl", self._handle_pnl))
        self.app.add_handler(CommandHandler("mode", self._handle_mode))
        self.app.add_handler(CommandHandler("aggressive", self._handle_aggressive))
        self.app.add_handler(CommandHandler("vanilla", self._handle_vanilla))
        self.app.add_handler(CommandHandler("help", self._handle_help))
        self._initialized = True

        logger.info("Telegram bot polling started")
        # Windows Python 3.11 requires explicit event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            self.app.run_polling()
        finally:
            loop.close()

    def _send_startup(self):
        if not self.chat_id or not self.app:
            return
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.send_message("◆ Kairo online."))
            loop.close()
        except Exception:
            pass

    async def send_message(self, text: str):
        if not self.app or not self.chat_id:
            return
        try:
            await self.app.bot.send_message(chat_id=int(self.chat_id), text=text)
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")

    async def send_trade_alert(self, trade: dict):
        symbol = trade.get("symbol", "?")
        side = trade.get("side", "?").upper()
        price = trade.get("entry_price", 0)
        size = trade.get("usdt_value", 0)
        sl = trade.get("stop_loss", 0)
        tp = trade.get("take_profit", 0)
        msg = (
            f"◆ *Trade*\n"
            f"`{symbol}` {side}\n"
            f"Price: ${price:.4f}\n"
            f"Size: ${size:.2f}\n"
            f"SL: ${sl:.4f} | TP: ${tp:.4f}"
        )
        await self.send_message(msg)

    async def send_close_alert(self, trade: dict):
        symbol = trade.get("symbol", "?")
        pnl = trade.get("pnl", 0)
        pnl_pct = trade.get("pnl_pct", 0)
        reason = trade.get("exit_reason", "manual")
        emoji = "△" if pnl > 0 else "▼"
        msg = (
            f"{emoji} *Closed*\n"
            f"`{symbol}`\n"
            f"PnL: ${pnl:.2f} ({pnl_pct:.1f}%)\n"
            f"Reason: {reason}"
        )
        await self.send_message(msg)

    async def send_daily_summary(self, journal_text: str):
        await self.send_message(journal_text)

    async def _handle_command(self, update: Update, command: str):
        user_id = update.effective_user.id
        result = self.killswitch.handle_command(command, user_id)
        await update.message.reply_text(result)

    async def _handle_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._handle_command(update, "/stop")

    async def _handle_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._handle_command(update, "/pause")

    async def _handle_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._handle_command(update, "/resume")

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._handle_command(update, "/status")

    async def _handle_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._handle_command(update, "/positions")

    async def _handle_pnl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._handle_command(update, "/pnl")

    # ------------------------------------------------------------------ #
    # Runtime mode switching (hot swap — zero restarts)
    # ------------------------------------------------------------------ #
    async def _authorized(self, update: Update) -> bool:
        user_id = update.effective_user.id if update.effective_user else None
        return user_id in self.killswitch.authorized_users

    @staticmethod
    def _mode_result_ok(result) -> bool:
        """Handle both bool (RuntimeStateManager) and dict (futures-aware
        StateManager subclass) return values from set_mode()."""
        if isinstance(result, dict):
            return bool(result.get("success", True))
        return bool(result)

    def _mode_summary(self, mode: str) -> str:
        if self.state is None:
            return "Mode switching disabled (no RuntimeStateManager)."
        status = self.state.status()
        return (
            f"◆ Mode: *{mode.upper()}*\n"
            f"Max position: {status['max_position_pct']:.1f}% | "
            f"Min conf: {status['min_confidence']:.2f}\n"
            f"Kelly: {status['kelly_fraction']:.2f} | "
            f"Risk/trade: {status['vol_target_risk_pct']*100:.1f}%\n"
            f"SL: {status['sl_atr_multiplier']:.1f}×ATR | "
            f"TP: {status['tp_atr_multiplier']:.1f}×ATR | "
            f"Min R:R: {status['min_risk_reward_ratio']:.1f}\n"
            f"Applies to next evaluation tick — no restart needed."
        )

    async def _handle_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._authorized(update):
            await update.message.reply_text("Unauthorized")
            return
        args = list(context.args or [])
        if not self.state:
            await update.message.reply_text("Mode switching disabled (no RuntimeStateManager).")
            return
        if not args or args[0].lower() not in ("vanilla", "aggressive"):
            await update.message.reply_text("Usage: /mode <vanilla|aggressive>")
            return
        mode = args[0].lower()
        result = self.state.set_mode(mode)
        if self._mode_result_ok(result):
            await update.message.reply_text(self._mode_summary(mode))
        else:
            await update.message.reply_text(f"Invalid mode: {mode}")

    async def _handle_aggressive(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._authorized(update):
            await update.message.reply_text("Unauthorized")
            return
        if self.state and self._mode_result_ok(self.state.set_mode("aggressive")):
            await update.message.reply_text(self._mode_summary("aggressive"))
        else:
            await update.message.reply_text("Mode switching disabled (no RuntimeStateManager).")

    async def _handle_vanilla(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._authorized(update):
            await update.message.reply_text("Unauthorized")
            return
        if self.state and self._mode_result_ok(self.state.set_mode("vanilla")):
            await update.message.reply_text(self._mode_summary("vanilla"))
        else:
            await update.message.reply_text("Mode switching disabled (no RuntimeStateManager).")

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "/stop — Kill switch\n"
            "/pause — Pause trading\n"
            "/resume — Resume\n"
            "/status — Current state\n"
            "/positions — Open positions\n"
            "/pnl — Profit/loss\n"
            "/mode <vanilla|aggressive> — Hot-swap risk profile\n"
            "/aggressive — Switch to aggressive profile\n"
            "/vanilla — Switch to vanilla profile"
        )
        await update.message.reply_text(help_text)
