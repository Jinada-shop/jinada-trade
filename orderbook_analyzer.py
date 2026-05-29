"""
Файл: orderbook_analyzer.py
Анализ стакана для точного входа.
"""

import asyncio
from typing import Dict, Optional

import requests

from config import config
from logger import logger


class OrderBookAnalyzer:
    """Анализ ордербука."""

    BASE_URL = "https://api.binance.com"

    def __init__(self):
        self.session = requests.Session()

    def get_orderbook(self, symbol: str, limit: int = 20) -> Optional[Dict]:
        """Получить стакан."""
        try:
            resp = self.session.get(
                f"{self.BASE_URL}/api/v3/depth",
                params={"symbol": symbol, "limit": limit},
                timeout=5,
            )
            data = resp.json()
            return {
                'bids': [[float(b[0]), float(b[1])] for b in data.get('bids', [])],
                'asks': [[float(a[0]), float(a[1])] for a in data.get('asks', [])],
            }
        except Exception as e:
            logger.error(f"Orderbook error: {e}")
            return None

    def analyze(self, symbol: str, signal_type: str) -> Dict:
        """
        Анализ стакана для сигнала.
        Возвращает рекомендацию: входить или ждать.
        """
        ob = self.get_orderbook(symbol)
        if not ob:
            return {'should_enter': True, 'reason': 'no_data', 'confidence': 0.5}

        bids = ob['bids']
        asks = ob['asks']

        # Сумма первых 10 уровней
        bid_volume = sum(b[1] for b in bids[:10])
        ask_volume = sum(a[1] for a in asks[:10])

        if bid_volume + ask_volume == 0:
            return {'should_enter': True, 'reason': 'no_liquidity', 'confidence': 0.5}

        # Дисбаланс
        imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)

        # Для BUY сигнала: хотим больше покупателей
        if signal_type == 'BUY':
            if imbalance > 0.2:
                return {'should_enter': True, 'reason': 'buyers_strong', 'confidence': 0.8}
            elif imbalance < -0.2:
                return {'should_enter': False, 'reason': 'sellers_strong', 'confidence': 0.3}
            else:
                return {'should_enter': True, 'reason': 'neutral', 'confidence': 0.6}
        else:
            if imbalance < -0.2:
                return {'should_enter': True, 'reason': 'sellers_strong', 'confidence': 0.8}
            elif imbalance > 0.2:
                return {'should_enter': False, 'reason': 'buyers_strong', 'confidence': 0.3}
            else:
                return {'should_enter': True, 'reason': 'neutral', 'confidence': 0.6}

    def get_best_limit_price(self, symbol: str, side: str) -> Optional[float]:
        """Лучшая цена для лимитного ордера."""
        ob = self.get_orderbook(symbol)
        if not ob:
            return None

        if side == 'BUY':
            # Чуть ниже лучшего аска
            if ob['bids']:
                return ob['bids'][0][0] * (1 + config.LIMIT_ORDER_OFFSET / 100)
        else:
            if ob['asks']:
                return ob['asks'][0][0] * (1 - config.LIMIT_ORDER_OFFSET / 100)
        return None