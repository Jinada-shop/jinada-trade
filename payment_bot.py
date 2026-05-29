"""
Файл: payment_bot.py — Telegram бот с подпиской
"""

import asyncio
from datetime import datetime, timedelta
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
import json
from pathlib import Path

from config import config

# Файл с подписчиками
SUBSCRIBERS_FILE = Path("subscribers.json")

def load_subscribers():
    if SUBSCRIBERS_FILE.exists():
        return json.loads(SUBSCRIBERS_FILE.read_text())
    return {}

def save_subscribers(data):
    SUBSCRIBERS_FILE.write_text(json.dumps(data, indent=2))

class PaymentBot:
    def __init__(self):
        self.bot = Bot(token=config.TELEGRAM_TOKEN)
        self.subscribers = load_subscribers()
    
    async def start(self, update: Update, context):
        """Приветственное сообщение"""
        user_id = str(update.effective_user.id)
        
        keyboard = [
            [InlineKeyboardButton("💳 Купить доступ", callback_data="buy")],
            [InlineKeyboardButton("📊 Демо-доступ (3 дня)", callback_data="demo")],
            [InlineKeyboardButton("ℹ️ О боте", callback_data="about")],
        ]
        
        text = """
🟡 *Jinada.Trade — AI Trading Platform*

Автоматическая торговля криптовалютой 24/7.

*Что ты получишь:*
✅ 4 торговые стратегии
✅ AI-прогнозы цен
✅ Авто-стопы и тейки
✅ Web-панель управления
✅ Сигналы в реальном времени

*Тарифы:*
💰 1 месяц — 9.90$
🔥 3 месяца — 24.90$ (скидка 16%)
🚀 12 месяцев — 79.90$ (скидка 33%)
        """
        
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_callback(self, update: Update, context):
        query = update.callback_query
        await query.answer()
        
        if query.data == "buy":
            await self.show_pricing(query)
        elif query.data == "demo":
            await self.activate_demo(query)
        elif query.data == "about":
            await self.show_about(query)
        elif query.data == "plan_1m":
            await self.process_payment(query, "1_month", 9.90)
        elif query.data == "plan_3m":
            await self.process_payment(query, "3_months", 24.90)
        elif query.data == "plan_12m":
            await self.process_payment(query, "12_months", 79.90)
    
    async def show_pricing(self, query):
        keyboard = [
            [InlineKeyboardButton("1 месяц — 9.90$", callback_data="plan_1m")],
            [InlineKeyboardButton("3 месяца — 24.90$", callback_data="plan_3m")],
            [InlineKeyboardButton("12 месяцев — 79.90$", callback_data="plan_12m")],
            [InlineKeyboardButton("« Назад", callback_data="start")],
        ]
        
        await query.edit_message_text(
            "*Выбери тариф:*\n\n"
            "💳 Оплата через Telegram Stars\n"
            "🌐 Или криптовалютой (BTC, USDT)",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def process_payment(self, query, plan, price):
        user_id = str(query.from_user.id)
        
        # Ссылка на оплату (замени на свою)
        payment_link = f"https://t.me/your_bot?start=pay_{plan}_{user_id}"
        
        keyboard = [
            [InlineKeyboardButton(f"💳 Оплатить {price}$ (Telegram Stars)", url="https://t.me/your_bot")],
            [InlineKeyboardButton("🪙 Оплатить криптой (BTC/USDT)", callback_data="crypto_pay")],
            [InlineKeyboardButton("« Назад", callback_data="buy")],
        ]
        
        await query.edit_message_text(
            f"*Тариф: {plan.replace('_', ' ')}*\n"
            f"Сумма: *{price}$*\n\n"
            "Выбери способ оплаты:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def activate_demo(self, query):
        user_id = str(query.from_user.id)
        
        if user_id in self.subscribers and self.subscribers[user_id].get('active'):
            await query.edit_message_text("У тебя уже есть активная подписка!")
            return
        
        # Активируем демо на 3 дня
        self.subscribers[user_id] = {
            'plan': 'demo',
            'expires': (datetime.now() + timedelta(days=3)).isoformat(),
            'active': True
        }
        save_subscribers(self.subscribers)
        
        await query.edit_message_text(
            "🎉 *Демо-доступ активирован на 3 дня!*\n\n"
            "Ты получил доступ к:\n"
            "✅ Сигналы в реальном времени\n"
            "✅ Web-панель управления\n"
            "✅ AI-прогнозы цен\n\n"
            "🔗 *Панель управления:* http://localhost:8501\n"
            "📱 Добавь API-ключи в настройках",
            parse_mode="Markdown"
        )
    
    async def show_about(self, query):
        keyboard = [[InlineKeyboardButton("« Назад", callback_data="start")]]
        await query.edit_message_text(
            "*Jinada.Trade v4.0*\n\n"
            "AI-Powered Trading Platform\n\n"
            "*Технологии:*\n"
            "• 4 торговые стратегии\n"
            "• Машинное обучение (Scikit-learn)\n"
            "• Прогноз цен на 24ч\n"
            "• HMM анализ рынка\n"
            "• Авто-стопы и тейки\n\n"
            "*Результаты тестов:*\n"
            "• 169 сделок\n"
            "• Винрейт: 55%+\n"
            "• Доходность: 7.8%/нед\n\n"
            "Связь: @your_username",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    def is_subscribed(self, user_id: str) -> bool:
        if user_id not in self.subscribers:
            return False
        
        sub = self.subscribers[user_id]
        if not sub.get('active'):
            return False
        
        expires = datetime.fromisoformat(sub['expires'])
        if datetime.now() > expires:
            sub['active'] = False
            save_subscribers(self.subscribers)
            return False
        
        return True
    
    def run(self):
        app = Application.builder().token(config.TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        print("Payment bot started!")
        app.run_polling()

if __name__ == "__main__":
    bot = PaymentBot()
    bot.run()