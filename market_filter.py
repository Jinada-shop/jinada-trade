"""
Файл: market_filter.py
Фильтры рынка: направление, аномалии, дни недели.
"""

from datetime import datetime
from typing import Dict, Optional

from config import config
from logger import logger


class MarketFilter:
    """Фильтры рынка."""

    def __init__(self, fetcher=None):
        self.fetcher = fetcher
        self.daily_trades = 0
        self.last_anomaly_alert = None

    async def get_market_direction(self) -> str:
        """Определение направления рынка по BTC."""
        if not self.fetcher:
            return "neutral"

        df = await self.fetcher("BTCUSDT", "1h", 24)
        if df.empty or len(df) < 24:
            return "neutral"

        change = (df['close'].iloc[-1] / df['close'].iloc[-24] - 1) * 100

        if change > 1:
            return "up"
        elif change < -1:
            return "down"
        return "neutral"

    def filter_signal(self, signal: Dict, market_direction: str) -> bool:
        """Фильтр сигнала по направлению рынка."""
        if not config.MARKET_DIRECTION_FILTER:
            return True

        if market_direction == "up" and signal['type'] == 'SELL':
            return False
        if market_direction == "down" and signal['type'] == 'BUY':
            return False

        return True

    async def check_anomaly(self, symbol: str) -> Optional[str]:
        """Проверка на аномальное движение."""
        if not self.fetcher:
            return None

        df = await self.fetcher(symbol, "5m", 12)
        if df.empty or len(df) < 12:
            return None

        change_1h = (df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100

        if abs(change_1h) > config.ANOMALY_ALERT_PCT:
            direction = "роста" if change_1h > 0 else "падения"
            return f"🚨 Аномалия {symbol}: {change_1h:+.1f}% за час ({direction})!"

        return None

    def check_daily_limit(self) -> bool:
        """Проверка дневного лимита сделок."""
        self.daily_trades += 1
        if self.daily_trades > config.DAILY_TRADE_LIMIT:
            return False
        return True

    def reset_daily(self):
        """Сброс дневного счётчика."""
        self.daily_trades = 0

    def get_weekday_config(self):
        """Настройки по дню недели."""
        if not config.WEEKDAY_FILTER:
            return None

        weekday = datetime.now().weekday()

        if weekday == 4:  # Пятница
            return {'max_positions': 1, 'risk_pct': 1.0}
        elif weekday == 6:  # Воскресенье
            return {'max_positions': 1, 'risk_pct': 0.5}
        elif weekday == 0:  # Понедельник
            return {'risk_pct': 1.5}

        return None