"""
Файл: alert_manager.py
Система умных уведомлений.
"""

from datetime import datetime
from typing import Dict, List, Optional

from config import config
from logger import logger


class AlertManager:
    """Управление уведомлениями."""

    def __init__(self, telegram_bot=None):
        self.bot = telegram_bot
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.last_report_day = None
        self.price_alerts: List[Dict] = []

    async def check_and_alert(self, event_type: str, data: Dict):
        """Проверить условия и отправить алерт."""
        alerts = []

        # 1. Сильный AI сигнал
        if event_type == "signal" and data.get("ai_signal") == "STRONG":
            alerts.append(
                f"🔥 <b>STRONG СИГНАЛ!</b>\n"
                f"📊 {data['symbol']} | AI: {data.get('ai_score', 0)*100:.0f}%\n"
                f"💰 {data['price']}"
            )

        # 2. Прибыльная сделка
        if event_type == "trade_closed":
            pnl = data.get("pnl", 0)
            self.daily_pnl += pnl
            self.daily_trades += 1

            if pnl > 0:
                alerts.append(
                    f"✅ <b>+{pnl:.2f}$</b> | {data['symbol']}\n"
                    f"📊 Баланс: {data.get('balance', 0):.2f}$"
                )

            # Проверка дневного профита
            if self.daily_pnl >= config.INITIAL_BALANCE * config.PROFIT_ALERT_PCT / 100:
                alerts.append(
                    f"🎉 <b>ДНЕВНАЯ ЦЕЛЬ!</b>\n"
                    f"💰 +{self.daily_pnl:.2f}$ (+{config.PROFIT_ALERT_PCT}%)"
                )

            # Проверка убытков
            if self.daily_pnl <= -config.INITIAL_BALANCE * config.LOSS_ALERT_PCT / 100:
                alerts.append(
                    f"⚠️ <b>СТОП НА СЕГОДНЯ</b>\n"
                    f"🔴 {self.daily_pnl:.2f}$ ({config.LOSS_ALERT_PCT}%)"
                )

        # 3. Аномалия
        if event_type == "anomaly":
            alerts.append(
                f"🚨 <b>АНОМАЛИЯ!</b>\n"
                f"📊 {data.get('symbol', '')} | {data.get('type', '')}\n"
                f"⚠️ Торговля приостановлена для этой пары"
            )

        # 4. Трейлинг-стоп активирован
        if event_type == "trailing_activated":
            alerts.append(
                f"📈 <b>Трейлинг-стоп!</b>\n"
                f"📊 {data['symbol']} | Новый стоп: {data['stop_loss']}"
            )

        # Отправка всех алертов
        for alert_text in alerts:
            await self._send(alert_text)

    async def _send(self, text: str):
        """Отправить алерт в канал."""
        if self.bot and self.bot.enabled:
            try:
                await self.bot.bot.send_message(
                    chat_id=config.TELEGRAM_CHAT_ID,
                    text=text,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Ошибка алерта: {e}")

    async def daily_report(self, balance: float, trades_count: int,
                          winning: int, total_pnl: float):
        """Ежедневный отчёт с графиком."""
        today = datetime.now().date()

        if self.last_report_day == today:
            return

        self.last_report_day = today

        win_rate = (winning / trades_count * 100) if trades_count > 0 else 0

        text = (
            f"📊 <b>ДНЕВНОЙ ОТЧЁТ</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"📅 {today.strftime('%d.%m.%Y')}\n"
            f"💰 Баланс: {balance:.2f}$\n"
            f"📈 Сделок: {trades_count}\n"
            f"✅ Винрейт: {win_rate:.0f}%\n"
            f"💵 PnL: {total_pnl:+.2f}$\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🕐 {datetime.now().strftime('%H:%M')}"
        )

        # Сброс дневной статистики
        self.daily_pnl = 0.0
        self.daily_trades = 0

        await self._send(text)

    def add_price_alert(self, symbol: str, condition: str, price: float):
        """Добавить алерт по цене."""
        self.price_alerts.append({
            "symbol": symbol,
            "condition": condition,
            "price": price,
            "created": datetime.now(),
        })

    def check_price_alerts(self, current_prices: Dict[str, float]) -> List[str]:
        """Проверить ценовые алерты."""
        triggered = []
        for alert in self.price_alerts[:]:
            symbol = alert["symbol"]
            if symbol in current_prices:
                current = current_prices[symbol]
                if alert["condition"] == ">" and current > alert["price"]:
                    triggered.append(f"🔔 {symbol} > {alert['price']}! Сейчас: {current}")
                    self.price_alerts.remove(alert)
                elif alert["condition"] == "<" and current < alert["price"]:
                    triggered.append(f"🔔 {symbol} < {alert['price']}! Сейчас: {current}")
                    self.price_alerts.remove(alert)
        return triggered