"""
Файл: telegram_bot.py — ПОЛНЫЙ МОНИТОРИНГ (ИСПРАВЛЕНО)
"""

import asyncio
import csv
import threading
from datetime import datetime
from io import BytesIO, StringIO
from typing import Dict, Optional

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters, ContextTypes,
)

from config import config
from database import get_db
from logger import logger


class TelegramBot:
    """Telegram-интерфейс с полным мониторингом."""

    def __init__(self, trading_system=None):
        if not config.TELEGRAM_TOKEN:
            self.enabled = False
            self.bot = None
            self.system = trading_system
            return

        self.enabled = True
        self.bot = Bot(token=config.TELEGRAM_TOKEN)
        self.system = trading_system
        self.app = Application.builder().token(config.TELEGRAM_TOKEN).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self._start))
        self.app.add_handler(CommandHandler("stats", self._stats))
        self.app.add_handler(CommandHandler("positions", self._positions))
        self.app.add_handler(CommandHandler("balance", self._balance))
        self.app.add_handler(CommandHandler("pause", self._pause))
        self.app.add_handler(CommandHandler("resume", self._resume))
        self.app.add_handler(CommandHandler("performance", self._performance))
        self.app.add_handler(CommandHandler("top", self._top))
        self.app.add_handler(CommandHandler("export", self._export))
        self.app.add_handler(CommandHandler("budget", self._budget))
        self.app.add_handler(CommandHandler("ai", self._ai))
        self.app.add_handler(CommandHandler("predict", self._predict))
        self.app.add_handler(CommandHandler("sentiment", self._sentiment))
        self.app.add_handler(CommandHandler("ultra", self._ultra))
        self.app.add_handler(CommandHandler("monitor", self._monitor))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._chat))
        self.app.add_handler(CallbackQueryHandler(self._callback))

    async def _start(self, update, context):
        text = (
            "🤖 Super Trading Bot v3.0\n\n"
            "/stats - Статистика\n"
            "/positions - Позиции\n"
            "/balance - Баланс\n"
            "/ai - AI отчёт\n"
            "/predict - Прогноз\n"
            "/sentiment - Сентимент\n"
            "/ultra - Ultra Scalping\n"
            "/monitor - Мониторинг\n"
            "/pause /resume - Пауза\n\n"
            "💬 Или просто напиши мне!"
        )
        kb = [[
            InlineKeyboardButton("📊 Статистика", callback_data="stats"),
            InlineKeyboardButton("💼 Позиции", callback_data="positions"),
        ]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

    async def _stats(self, update, context):
        with get_db() as db:
            total = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED'").fetchone()[0]
            wins = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED' AND pnl>0").fetchone()[0]
            pnl = db.execute("SELECT SUM(pnl) FROM trades WHERE status='CLOSED'").fetchone()[0] or 0
            today = db.execute("SELECT COUNT(*), SUM(pnl) FROM trades WHERE status='CLOSED' AND date(exit_time)=date('now')").fetchone()
        wr = (wins / total * 100) if total > 0 else 0
        text = f"📊 Статистика\nСделок: {total}\nВинрейт: {wr:.0f}%\nPnL: {pnl:+.2f}$\nСегодня: {today[0] or 0} сделок, {today[1] or 0:+.2f}$"
        await update.message.reply_text(text)

    async def _positions(self, update, context):
        if not self.system:
            await update.message.reply_text("Система не запущена")
            return
        if not self.system.open_positions:
            await update.message.reply_text("💼 Нет открытых позиций")
            return
        text = "💼 ОТКРЫТЫЕ ПОЗИЦИИ:\n\n"
        for i, pos in enumerate(self.system.open_positions, 1):
            exchange = pos.get('exchange', 'binance')
            text += (
                f"{i}. {pos['symbol']} ({pos['type']}) @ {pos['price']}\n"
                f"   Биржа: {exchange.upper()}\n"
                f"   Стоп: {pos.get('stop_loss', 'N/A')}\n"
                f"   Тейк: {pos.get('take_profit', 'N/A')}\n"
                f"   Кол-во: {pos.get('quantity', 0):.6f}\n\n"
            )
        await update.message.reply_text(text)

    async def _balance(self, update, context):
        if not self.system:
            await update.message.reply_text("Система не запущена")
            return
        bal = self.system.balance
        pnl = self.system.total_profit
        us_profit = self.system.ultra_scalping.total_profit if hasattr(self.system, 'ultra_scalping') else 0
        text = (
            f"💰 БАЛАНС: {bal:.2f}$\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 Общий PnL: {pnl:+.2f}$\n"
            f"⚡ Ultra Scalping: {us_profit:+.4f}$\n"
            f"📊 Сделок сегодня: {self.system.daily_trades}\n"
        )
        await update.message.reply_text(text)

    async def _pause(self, update, context):
        if self.system:
            self.system.paused = True
        await update.message.reply_text("⏸ Торговля приостановлена")

    async def _resume(self, update, context):
        if self.system:
            self.system.paused = False
        await update.message.reply_text("▶️ Торговля возобновлена")

    async def _performance(self, update, context):
        with get_db() as db:
            total = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED'").fetchone()[0]
            wins = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED' AND pnl>0").fetchone()[0]
            pnl = db.execute("SELECT SUM(pnl) FROM trades WHERE status='CLOSED'").fetchone()[0] or 0
            best = db.execute("SELECT symbol, MAX(pnl) FROM trades WHERE status='CLOSED'").fetchone()
            worst = db.execute("SELECT symbol, MIN(pnl) FROM trades WHERE status='CLOSED'").fetchone()
        wr = (wins / total * 100) if total > 0 else 0
        text = (
            f"📊 PERFORMANCE\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Сделок: {total}\nВинрейт: {wr:.0f}%\nPnL: {pnl:+.2f}$\n"
            f"Лучшая: {best[0]} ({best[1]:+.2f}$)\nХудшая: {worst[0]} ({worst[1]:+.2f}$)"
        )
        await update.message.reply_text(text)

    async def _top(self, update, context):
        with get_db() as db:
            best = db.execute("SELECT symbol, SUM(pnl) as pnl FROM trades WHERE status='CLOSED' GROUP BY symbol ORDER BY pnl DESC LIMIT 5").fetchall()
        text = "🟢 Топ-5 пар:\n"
        for r in best:
            text += f"  {r['symbol']}: {r['pnl']:+.2f}$\n"
        await update.message.reply_text(text)

    async def _export(self, update, context):
        with get_db() as db:
            rows = db.execute("SELECT * FROM trades WHERE status='CLOSED' ORDER BY exit_time DESC LIMIT 500").fetchall()
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["symbol", "direction", "entry_price", "exit_price", "pnl", "exit_reason", "strategy", "entry_time", "exit_time"])
        for r in rows:
            writer.writerow([r['symbol'], r['direction'], r['entry_price'], r['exit_price'], r['pnl'], r['exit_reason'], r['strategy'], r['entry_time'], r['exit_time']])
        output.seek(0)
        await update.message.reply_document(document=BytesIO(output.getvalue().encode()), filename=f"trades_{datetime.now().strftime('%Y%m%d')}.csv", caption="📊 Отчёт")

    async def _budget(self, update, context):
        if not self.system:
            await update.message.reply_text("Система не запущена")
            return
        status = self.system.budget.get_status(self.system.balance, self.system.open_positions)
        await update.message.reply_text(status)

    async def _ai(self, update, context):
        """AI отчёт — использует chatgpt_deep."""
        if not self.system or not hasattr(self.system, 'chatgpt_deep'):
            await update.message.reply_text("AI не доступен")
            return
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        report = await self.system.chatgpt_deep.analyze_market(config.SYMBOLS)
        await update.message.reply_text(report)

    async def _predict(self, update, context):
        """Прогноз — использует chatgpt_deep."""
        if not self.system or not hasattr(self.system, 'chatgpt_deep'):
            await update.message.reply_text("AI не доступен")
            return
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        text = "📈 ПРОГНОЗ НА 24Ч\n\n"
        for sym in config.SYMBOLS:
            try:
                pred = await self.system.chatgpt_deep.predict_market(sym)
                text += f"{sym}: {pred}\n\n"
            except Exception:
                text += f"{sym}: нет данных\n"
        await update.message.reply_text(text)

    async def _sentiment(self, update, context):
        """Сентимент — использует sentiment."""
        if not self.system or not hasattr(self.system, 'sentiment'):
            await update.message.reply_text("Сентимент не доступен")
            return
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        sent = await self.system.sentiment.comprehensive("BTCUSDT")
        fg = sent.get('fear_greed', {})
        await update.message.reply_text(
            f"🧠 Сентимент\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Страх/Жадность: {fg.get('value', 50)} ({fg.get('classification', 'Neutral')})\n"
            f"Сигнал: {sent.get('signal', 'neutral')}\n"
            f"Уверенность: {sent.get('confidence', 0):.0%}"
        )

    async def _ultra(self, update, context):
        if not self.system or not hasattr(self.system, 'ultra_scalping'):
            await update.message.reply_text("Ultra Scalping не доступен")
            return
        stats = self.system.ultra_scalping.get_stats()
        await update.message.reply_text(stats)

    async def _monitor(self, update, context):
        """Полный мониторинг состояния."""
        if not self.system:
            await update.message.reply_text("Система не запущена")
            return
        us_stats = self.system.ultra_scalping.get_stats() if hasattr(self.system, 'ultra_scalping') else "Нет данных"
        reconnect_status = self.system.reconnect.get_status() if hasattr(self.system, 'reconnect') else "Нет данных"
        text = (
            f"📊 МОНИТОРИНГ\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Баланс: {self.system.balance:.2f}$\n"
            f"📈 PnL: {self.system.total_profit:+.2f}$\n"
            f"💼 Позиций: {len(self.system.open_positions)}\n"
            f"📉 Сделок сегодня: {self.system.daily_trades}\n"
            f"⏸ Статус: {'Пауза' if self.system.paused else 'Работает'}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{us_stats}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{reconnect_status}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        await update.message.reply_text(text)

    async def _chat(self, update, context):
        user_id = update.effective_user.id
        username = update.effective_user.username or "User"
        message = update.message.text
        if self.system and hasattr(self.system, 'companion'):
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            reply = await self.system.companion.chat(user_id, username, message)
            await update.message.reply_text(reply)
        else:
            await update.message.reply_text("👋 Привет! Спрашивай что угодно!")

    async def _callback(self, update, context):
        query = update.callback_query
        await query.answer()
        if query.data == "stats":
            await self._stats(update, context)
        elif query.data == "positions":
            await self._positions(update, context)

    # ================================================================
    # УВЕДОМЛЕНИЯ В КАНАЛ
    # ================================================================

    async def send_signal(self, signal: Dict, chart: Optional[BytesIO] = None):
        if not self.enabled or not config.TELEGRAM_CHAT_ID:
            return
        emoji = "🟢" if signal["type"] == "BUY" else "🔴"
        direction = "ПОКУПКА" if signal["type"] == "BUY" else "ПРОДАЖА"
        text = (
            f"{emoji} {direction}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 {signal['symbol']}\n"
            f"🎯 {signal.get('strategy', '-')}\n"
            f"💰 Цена: {signal.get('price', 0)}\n"
            f"💡 Уверенность: {signal.get('confidence', 0)*100:.0f}%\n"
            f"🤖 AI: {signal.get('ai_signal', '-')} ({signal.get('ai_score', 0)*100:.0f}%)\n"
            f"📈 RSI: {signal.get('rsi', '-')}\n"
            f"🛑 Стоп: {signal.get('stop_loss', 'N/A')}\n"
            f"🎯 Тейк: {signal.get('take_profit', 'N/A')}\n"
            f"⏳ {signal.get('time_summary', '')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        try:
            if chart:
                await self.bot.send_photo(chat_id=config.TELEGRAM_CHAT_ID, photo=chart, caption=text[:1024])
            else:
                await self.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)
        except Exception as e:
            logger.error(f"Ошибка отправки сигнала: {e}")

    async def send_trade_notification(self, trade_type: str, details: Dict):
        if not self.enabled or not config.TELEGRAM_CHAT_ID:
            return
        if trade_type == "open":
            emoji = "🟢" if details.get('type') == 'BUY' else "🔴"
            text = (
                f"{emoji} <b>СДЕЛКА ОТКРЫТА</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 {details.get('symbol')}\n"
                f"🏦 {details.get('exchange', 'Binance').upper()}\n"
                f"💰 Цена: {details.get('price', 0)}\n"
                f"📦 Кол-во: {details.get('quantity', 0):.6f}\n"
                f"💵 Потрачено: {details.get('total_spent', 0):.2f}$\n"
                f"🤖 AI: {details.get('ai_signal', '-')}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🕐 {datetime.now().strftime('%H:%M:%S')}"
            )
        elif trade_type == "close":
            emoji = "🟢" if details.get('pnl', 0) > 0 else "🔴"
            text = (
                f"{emoji} <b>СДЕЛКА ЗАКРЫТА</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 {details.get('symbol')}\n"
                f"💰 PnL: {details.get('pnl', 0):+.2f}$\n"
                f"💵 Баланс: {details.get('balance', 0):.2f}$\n"
                f"📝 Причина: {details.get('reason', '-')}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🕐 {datetime.now().strftime('%H:%M:%S')}"
            )
        elif trade_type == "ultra":
            emoji = "🟢" if details.get('profit', 0) > 0 else "🔴"
            text = (
                f"⚡ <b>ULTRA SCALPING</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 {details.get('symbol')}\n"
                f"💰 Прибыль: {details.get('profit', 0):+.4f}$\n"
                f"📈 Всего сделок US: {details.get('total_trades', 0)}\n"
                f"💵 Общая прибыль US: {details.get('total_profit', 0):+.4f}$\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🕐 {datetime.now().strftime('%H:%M:%S')}"
            )
        else:
            return
        try:
            await self.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")

    async def send_alert(self, message: str):
        if not self.enabled or not config.TELEGRAM_CHAT_ID:
            return
        try:
            await self.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=f"🚨 {message}\n🕐 {datetime.now().strftime('%H:%M:%S')}"
            )
        except Exception:
            pass

    # ================================================================
    # ЗАПУСК
    # ================================================================

    def start(self):
        if not self.enabled:
            return
        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            async def _init():
                await self.app.initialize()
                await self.app.start()
                await self.app.updater.start_polling()
                logger.info("Telegram бот запущен")
            loop.run_until_complete(_init())
            loop.run_forever()
        threading.Thread(target=_run, daemon=True).start()

    async def send_message(self, text: str):
        if self.enabled and config.TELEGRAM_CHAT_ID:
            try:
                await self.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)
            except Exception:
                pass

    async def send_photo(self, photo: BytesIO, caption: str = ""):
        if self.enabled and config.TELEGRAM_CHAT_ID:
            try:
                await self.bot.send_photo(chat_id=config.TELEGRAM_CHAT_ID, photo=photo, caption=caption[:1024])
            except Exception:
                pass