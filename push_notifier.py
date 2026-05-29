"""
Файл: push_notifier.py
Push-уведомления через ntfy.sh (бесплатно, без регистрации).
"""

import requests

from config import config
from logger import logger


class PushNotifier:
    """Отправка push-уведомлений."""

    def __init__(self):
        self.topic = config.NTFY_TOPIC or "trading_bot_alerts"
        self.base_url = f"https://ntfy.sh/{self.topic}"

    def send(self, title: str, message: str, priority: str = "default"):
        """Отправить уведомление."""
        if not config.PUSH_NOTIFICATIONS:
            return

        try:
            requests.post(
                self.base_url,
                data=message.encode('utf-8'),
                headers={
                    "Title": title,
                    "Priority": priority,
                    "Tags": "chart_with_upwards_trend",
                },
                timeout=5,
            )
        except Exception as e:
            logger.error(f"Push ошибка: {e}")

    def send_trade_opened(self, symbol: str, price: float):
        self.send("Новая сделка!", f"{symbol} @ {price}", "high")

    def send_trade_closed(self, symbol: str, pnl: float):
        emoji = "🟢" if pnl > 0 else "🔴"
        self.send(f"{emoji} Сделка закрыта", f"{symbol}: {pnl:+.2f}$", "high")

    def send_record(self, balance: float):
        self.send("🏆 Новый рекорд!", f"Баланс: {balance:.2f}$", "max")

    def send_alert(self, message: str):
        self.send("⚠️ Алерт", message, "max")