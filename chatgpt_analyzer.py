"""
Файл: chatgpt_analyzer.py
Интеграция с ChatGPT для анализа сделок.
"""

import json

import requests

from config import config
from database import get_db
from logger import logger


class ChatGPTAnalyzer:
    """Анализ через OpenAI API."""

    def __init__(self):
        self.api_key = config.OPENAI_API_KEY
        self.enabled = bool(self.api_key) and config.CHATGPT_ANALYSIS

    def analyze_trades(self) -> str:
        """Анализ последних сделок."""
        if not self.enabled:
            return "ChatGPT отключён (нет API ключа)"

        with get_db() as db:
            trades = db.execute(
                "SELECT symbol, direction, pnl, exit_reason, strategy "
                "FROM trades WHERE status='CLOSED' ORDER BY exit_time DESC LIMIT 20"
            ).fetchall()

        if not trades:
            return "Нет данных для анализа"

        trade_text = "\n".join([
            f"{t['symbol']} {t['direction']}: {t['pnl']:+.2f}$ ({t['exit_reason']}) [{t['strategy']}]"
            for t in trades
        ])

        prompt = f"""
        Я торговый бот. Проанализируй мои последние 20 сделок и дай краткие рекомендации (3-5 пунктов) что улучшить.
        Вот сделки:
        {trade_text}
        
        Ответь на русском, кратко, по делу.
        """

        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.7,
                },
                timeout=30,
            )
            data = resp.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"ChatGPT ошибка: {e}")
            return f"Ошибка анализа: {e}"

    def analyze_market_sentiment(self, fear_greed: int, btc_change: float) -> str:
        """Анализ рыночных условий."""
        if not self.enabled:
            return ""

        prompt = f"""
        Индекс страха и жадности: {fear_greed}
        Изменение BTC за час: {btc_change:+.2f}%
        
        Дай краткую рекомендацию по торговле на ближайшие 4 часа. 1-2 предложения на русском.
        """

        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                },
                timeout=15,
            )
            return resp.json()['choices'][0]['message']['content']
        except Exception:
            return ""