"""
Файл: ai_companion.py
СВОБОДНЫЙ AI ЧАТ — отвечает на ЛЮБЫЕ вопросы как ChatGPT
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import requests

from config import config
from database import get_db
from logger import logger


class AICompanion:
    """
    Свободный AI собеседник.
    Отвечает на ЛЮБЫЕ вопросы, не только про трейдинг.
    """

    def __init__(self, fetcher=None, telegram=None):
        self.fetcher = fetcher
        self.telegram = telegram
        self.openai_key = getattr(config, 'OPENAI_API_KEY', '')
        self.deepseek_key = getattr(config, 'DEEPSEEK_API_KEY', '')

        if self.deepseek_key:
            self.api_key = self.deepseek_key
            self.api_url = "https://api.deepseek.com/v1/chat/completions"
            self.model = "deepseek-chat"
        elif self.openai_key:
            self.api_key = self.openai_key
            self.api_url = "https://api.openai.com/v1/chat/completions"
            self.model = "gpt-3.5-turbo"
        else:
            self.api_key = ""
            self.api_url = ""
            self.model = ""

        self.use_api = bool(self.api_key)
        self.conversation_history: Dict[int, List[Dict]] = {}

    def _call_api(self, messages: list, max_tokens: int = 500) -> Optional[str]:
        """Вызов API."""
        if not self.use_api:
            return None

        try:
            resp = requests.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.8,
                },
                timeout=20,
            )
            data = resp.json()
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"API ошибка: {e}")
        return None

    # ================================================================
    async def chat(self, user_id: int, username: str, message: str) -> str:
        """
        СВОБОДНЫЙ ЧАТ — отвечает на любые вопросы.
        """
        # Статистика для контекста (если вопрос про трейдинг)
        stats = self._get_stats()
        pnl = self._get_pnl()

        # История разговора
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []

        # Системный промпт — универсальный ассистент
        system_prompt = f"""
        Ты — дружелюбный AI ассистент. Ты отвечаешь на ЛЮБЫЕ вопросы пользователя.
        
        Стиль общения:
        - Дружелюбный и полезный
        - Отвечаешь кратко но информативно
        - Если вопрос про трейдинг или крипту — используешь статистику бота
        - Если вопрос на любую другую тему — отвечаешь как обычный AI
        - Используешь эмодзи для настроения
        
        Статистика торгового бота (если спросят):
        {stats}
        Общий PnL: {pnl:+.2f}$
        
        Отвечай на русском языке.
        """

        messages = [{"role": "system", "content": system_prompt}]

        # Добавляем историю (последние 15 сообщений)
        for msg in self.conversation_history[user_id][-15:]:
            messages.append(msg)

        # Добавляем новое сообщение
        messages.append({"role": "user", "content": message})

        # Пробуем API
        if self.use_api:
            reply = self._call_api(messages)
            if reply:
                self.conversation_history[user_id].append({"role": "user", "content": message})
                self.conversation_history[user_id].append({"role": "assistant", "content": reply})
                return reply

        # Локальный ответ
        return self._local_reply(message, stats, pnl)

    def _local_reply(self, message: str, stats: str, pnl: float) -> str:
        """Локальные ответы без API."""
        msg = message.lower()

        # Приветствия
        if any(w in msg for w in ['привет', 'здрав', 'хай', 'hello', 'добрый']):
            return f"👋 Привет! Я AI ассистент. Спрашивай что угодно — я отвечу!\n\n{stats}"

        # Трейдинг
        if any(w in msg for w in ['винрейт', 'winrate', 'процент побед']):
            return stats
        if any(w in msg for w in ['прибыль', 'pnl', 'заработал', 'доход', 'сколько денег']):
            return f"💰 Общая прибыль бота: {pnl:+.2f}$\n\n{stats}"
        if any(w in msg for w in ['совет', 'рекомендац', 'что делать', 'как улучшить', 'что посоветуешь']):
            return self._get_advice()
        if any(w in msg for w in ['стратег', 'strategy']):
            return "🎯 Бот использует 3 стратегии: Scalping (пробои), Trend (откаты), CounterTrend (уровни)."
        if any(w in msg for w in ['риск', 'risk']):
            return f"⚠️ Риск на сделку: {config.RISK_PER_TRADE_PCT}%\nМакс позиций: {config.MAX_POSITIONS}"
        if any(w in msg for w in ['биржа', 'exchange', 'где торгуешь']):
            return "🏦 Бот подключён к Binance и Bybit. Торгует на споте."

        # О себе
        if any(w in msg for w in ['кто ты', 'что ты', 'who are', 'что умеешь']):
            return (
                "🤖 Я — AI ассистент торгового бота.\n\n"
                "Что я умею:\n"
                "📊 Показывать статистику сделок\n"
                "💰 Отвечать на вопросы о прибыли\n"
                "💡 Давать советы по трейдингу\n"
                "📈 Прогнозировать цены\n"
                "💬 Общаться на любые темы\n\n"
                "Спрашивай что угодно!"
            )

        if any(w in msg for w in ['спасибо', 'благодар', 'спс']):
            return "🙏 Всегда пожалуйста! Рад помочь!"

        if any(w in msg for w in ['пока', 'до свидан', 'bye', 'увидимся']):
            return "👋 До встречи! Удачи и зелёных графиков! 🚀"

        if any(w in msg for w in ['как дела', 'как ты', 'how are']):
            if pnl > 0:
                return f"😊 Отлично! Бот в плюсе на {pnl:+.2f}$. Настроение боевое!"
            else:
                return f"😔 Нормально, но бот пока в минусе ({pnl:+.2f}$). Работаю над улучшениями!"

        # Общие темы
        if any(w in msg for w in ['погода', 'weather']):
            return "🌤 Я не смотрю погоду, но могу рассказать о крипто-климате! Рынок сейчас нейтральный."

        if any(w in msg for w in ['шутк', 'анекдот', 'joke', 'смешн']):
            return (
                "😂 Почему трейдер не может уснуть?\n"
                "Потому что ему всё время кажется что он пропустил идеальный вход!\n\n"
                "Хочешь ещё?"
            )

        if any(w in msg for w in ['биткоин', 'bitcoin', 'btc', 'биток']):
            return (
                "₿ Биткоин — король крипты!\n"
                f"{stats}\n"
                "Хочешь прогноз цены? Напиши /predict BTCUSDT"
            )

        # Ответ по умолчанию
        return (
            f"🤔 Интересный вопрос! Вот что я могу рассказать:\n\n"
            f"{stats}\n\n"
            f"Или спроси о чём-то ещё — я постараюсь помочь! 💡"
        )

    # ================================================================
    async def auto_advice(self) -> Optional[str]:
        """Автоматический совет."""
        stats = self._get_stats()
        pnl = self._get_pnl()
        messages = []

        with get_db() as db:
            last_5 = db.execute(
                "SELECT pnl FROM trades WHERE status='CLOSED' ORDER BY exit_time DESC LIMIT 5"
            ).fetchall()

        if len(last_5) >= 5:
            losses = sum(1 for r in last_5 if (r[0] or 0) < 0)
            if losses >= 4:
                messages.append(
                    f"⚠️ Внимание! {losses}/5 последних сделок убыточны.\n"
                    f"Рекомендую уменьшить риск и проверить стратегии."
                )

        with get_db() as db:
            today_pnl = db.execute(
                "SELECT SUM(pnl) FROM trades WHERE status='CLOSED' AND date(exit_time)=date('now')"
            ).fetchone()[0] or 0

        if today_pnl > 10:
            messages.append(f"🎉 Отличный день! +{today_pnl:.2f}$ сегодня! Так держать! 🚀")

        for msg in messages:
            if self.telegram:
                await self.telegram.send_message(msg)

        return None

    async def market_update(self):
        """Обновление о рынке."""
        if not self.telegram:
            return

        stats = self._get_stats()
        pnl = self._get_pnl()
        btc_price = "N/A"

        if self.fetcher:
            df = await self.fetcher("BTCUSDT", "1h", 2)
            if not df.empty:
                btc_price = f"{df['close'].iloc[-1]:.0f}$"
                change = (df['close'].iloc[-1] / df['close'].iloc[-2] - 1) * 100
                btc_price += f" ({change:+.2f}%)"

        with get_db() as db:
            today = db.execute(
                "SELECT COUNT(*), SUM(pnl) FROM trades WHERE status='CLOSED' AND date(exit_time)=date('now')"
            ).fetchone()

        prompt = f"""
        Ты — дружелюбный AI ассистент трейдера. Напиши короткое обновление о рынке (2-3 предложения).
        BTC: {btc_price}
        Сделок сегодня: {today[0] or 0}, PnL: {today[1] or 0:+.2f}$
        Общий PnL: {pnl:+.2f}$
        Будь позитивным, дай совет.
        """

        if self.use_api:
            result = self._call_api([{"role": "user", "content": prompt}])
            if result:
                await self.telegram.send_message(f"📊 {result}")
                return

        await self.telegram.send_message(
            f"📊 Обновление рынка\n"
            f"₿ BTC: {btc_price}\n"
            f"📈 Сегодня: {today[0] or 0} сделок, PnL: {today[1] or 0:+.2f}$\n"
            f"💰 Общий PnL: {pnl:+.2f}$\n"
            f"💡 {self._get_advice()}"
        )

    # ================================================================
    def _get_stats(self) -> str:
        with get_db() as db:
            total = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED'").fetchone()[0]
            wins = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED' AND pnl>0").fetchone()[0]
            pnl = db.execute("SELECT SUM(pnl) FROM trades WHERE status='CLOSED'").fetchone()[0] or 0
            open_pos = db.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'").fetchone()[0]

        wr = (wins / total * 100) if total > 0 else 0
        return f"📊 Сделок: {total} | Винрейт: {wr:.0f}% | PnL: {pnl:+.2f}$ | Открыто: {open_pos}"

    def _get_pnl(self) -> float:
        with get_db() as db:
            return db.execute("SELECT SUM(pnl) FROM trades WHERE status='CLOSED'").fetchone()[0] or 0

    def _get_advice(self) -> str:
        with get_db() as db:
            total = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED'").fetchone()[0]
            wins = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED' AND pnl>0").fetchone()[0]
            pnl = db.execute("SELECT SUM(pnl) FROM trades WHERE status='CLOSED'").fetchone()[0] or 0

        wr = (wins / total * 100) if total > 0 else 0

        if total < 20:
            return "Нужно больше сделок для анализа. Продолжай торговать."
        if wr >= 55:
            return "Отличный винрейт! Можно увеличить риск до 3-4%."
        if wr >= 45:
            return "Хороший результат. Держи риск на текущем уровне."
        if wr >= 35:
            return "Средний винрейт. Проверь убыточные пары и исключи их."
        return "Низкий винрейт. Рекомендую уменьшить риск и торговать только BTC/ETH."