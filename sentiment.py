"""
Файл: sentiment.py
Анализ сентимента (через requests).
"""

from typing import Dict

import requests

from cache import cache
from logger import logger


class SentimentAnalyzer:
    """Анализатор сентимента."""

    def __init__(self):
        self.session = requests.Session()

    async def get_fear_greed(self) -> Dict:
        """Индекс страха и жадности."""
        cached = cache.get("fear_greed")
        if cached:
            return cached

        try:
            resp = self.session.get(
                "https://api.alternative.me/fng/?limit=1",
                timeout=10,
            )
            data = resp.json()

            if data and "data" in data:
                result = {
                    "value": int(data["data"][0]["value"]),
                    "classification": data["data"][0]["value_classification"],
                }
                cache.set("fear_greed", result)
                return result
        except Exception as e:
            logger.error(f"Fear & Greed ошибка: {e}")

        return {"value": 50, "classification": "Neutral"}

    def analyze_text(self, text: str) -> float:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            analyzer = SentimentIntensityAnalyzer()
            return analyzer.polarity_scores(text)["compound"]
        except ImportError:
            return 0.0

    async def comprehensive(self, symbol: str) -> Dict:
        fg = await self.get_fear_greed()
        fg_score = (fg["value"] - 50) / 50

        return {
            "fear_greed": fg,
            "composite_score": fg_score,
            "signal": (
                "bullish_contrarian"
                if fg_score < -0.3
                else "bearish_contrarian"
                if fg_score > 0.3
                else "neutral"
            ),
            "confidence": abs(fg_score),
        }

    async def close(self):
        self.session.close()