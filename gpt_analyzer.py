"""
Файл: gpt_analyzer.py
AI анализ рыночных условий (OpenAI API).
"""

import os
from typing import Dict, Optional

import requests

from logger import logger


class GPTAnalyzer:
    """GPT анализ рынка (работает без API ключа — базовая логика)."""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.use_api = bool(self.api_key)

    def analyze_market(self, heatmap_data: Dict, sentiment: Dict) -> Dict:
        """
        Анализ рынка.
        Если есть OpenAI ключ — использует GPT.
        Если нет — базовая логика.
        """
        if self.use_api:
            return self._gpt_analysis(heatmap_data, sentiment)
        return self._basic_analysis(heatmap_data, sentiment)

    def _basic_analysis(self, heatmap: Dict, sentiment: Dict) -> Dict:
        """Базовая логика без GPT."""
        gainers = len(heatmap.get('top_gainers', []))
        losers = len(heatmap.get('top_losers', []))
        fg = sentiment.get('fear_greed', {}).get('value', 50)

        # Оценка рынка
        if fg <= 25:
            market_mood = "Экстремальный страх — возможен разворот вверх"
            action = "Покупать осторожно"
        elif fg <= 45:
            market_mood = "Страх — рынок падает"
            action = "Ждать подтверждения"
        elif fg <= 55:
            market_mood = "Нейтрально"
            action = "Торговать по стратегии"
        elif fg <= 75:
            market_mood = "Жадность — рынок растёт"
            action = "Торговать по тренду"
        else:
            market_mood = "Экстремальная жадность — возможна коррекция"
            action = "Фиксировать прибыль"

        # Анализ движения
        if gainers > losers * 2:
            trend = "Бычий"
        elif losers > gainers * 2:
            trend = "Медвежий"
        else:
            trend = "Смешанный"

        return {
            'market_mood': market_mood,
            'trend': trend,
            'action': action,
            'gainers_count': gainers,
            'losers_count': losers,
            'fear_greed': fg,
            'should_trade': fg <= 75,
            'risk_level': 'Высокий' if fg >= 75 or fg <= 25 else 'Средний' if 45 <= fg <= 55 else 'Низкий',
        }

    def _gpt_analysis(self, heatmap: Dict, sentiment: Dict) -> Dict:
        """GPT анализ (требует API ключ)."""
        prompt = f"""
        Проанализируй рынок криптовалют:
        Топ растущих: {heatmap.get('top_gainers', [])[:3]}
        Топ падающих: {heatmap.get('top_losers', [])[:3]}
        Индекс страха: {sentiment.get('fear_greed', {}).get('value', 50)}
        
        Дай краткий ответ: настроение рынка, тренд, рекомендацию, стоит ли торговать.
        Ответь в JSON: {{"mood": "", "trend": "", "action": "", "should_trade": true/false, "risk": ""}}
        """

        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                },
                timeout=15,
            )
            data = resp.json()
            content = data['choices'][0]['message']['content']
            import json
            return json.loads(content)
        except Exception as e:
            logger.error(f"GPT ошибка: {e}")
            return self._basic_analysis(heatmap, sentiment)