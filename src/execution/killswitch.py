"""Kill Switch — Telegram-controlled emergency stop.
Responds to /stop, /pause, /resume commands.
Instantly liquidates all positions when triggered."""

from loguru import logger


class KillSwitch:
    def __init__(self, paper_trader, live_trader=None):
        self.paper = paper_trader
        self.live = live_trader
        self.is_paused = False
        self.is_stopped = False
        self.authorized_users: set = set()

    def add_authorized_user(self, user_id: int):
        self.authorized_users.add(user_id)

    def handle_command(self, command: str, user_id: int) -> str:
        if user_id not in self.authorized_users:
            logger.warning(f"Unauthorized kill command from user {user_id}")
            return "Unauthorized"

        cmd = command.lower().strip()

        if cmd == "/stop":
            self.is_stopped = True
            self.is_paused = True
            self.paper.close_all("kill_switch")
            logger.critical("KILL SWITCH ACTIVATED — all positions closed")
            return "KILL SWITCH: All positions closed. Bot stopped."

        elif cmd == "/pause":
            self.is_paused = True
            logger.warning("Trading PAUSED")
            return "Trading PAUSED. Use /resume to continue."

        elif cmd == "/resume":
            if self.is_stopped:
                return "Bot was STOPPED. Manual restart required."
            self.is_paused = False
            logger.info("Trading RESUMED")
            return "Trading RESUMED."

        elif cmd == "/status":
            return self.get_status()

        elif cmd == "/positions":
            portfolio = self.paper.get_portfolio()
            if portfolio["open_positions"] == 0:
                return "No open positions."
            trades = portfolio["open_trades"]
            lines = [f"{t['side'].upper()} {t['symbol']} @ {t['entry_price']} | SL: {t['stop_loss']} | TP: {t['take_profit']}" for t in trades]
            return "Open positions:\n" + "\n".join(lines)

        elif cmd == "/pnl":
            portfolio = self.paper.get_portfolio()
            return f"Balance: ${portfolio['balance']:.2f}\nToday P&L: ${portfolio.get('daily_pnl', 0):.2f}\nOpen: {portfolio['open_positions']}"

        else:
            return f"Unknown command: {command}"

    def get_status(self) -> str:
        state = "STOPPED" if self.is_stopped else "PAUSED" if self.is_paused else "RUNNING"
        portfolio = self.paper.get_portfolio()
        return (
            f"Status: {state}\n"
            f"Balance: ${portfolio['balance']:.2f}\n"
            f"Open positions: {portfolio['open_positions']}\n"
            f"Total trades: {portfolio['total_trades']}"
        )

    def trading_allowed(self) -> bool:
        return not (self.is_paused or self.is_stopped)
