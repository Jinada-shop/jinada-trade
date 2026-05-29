"""
Файл: websocket_stream.py
WebSocket стрим цен Binance.
"""

import asyncio
import json
from typing import Callable, Dict

import websockets

from logger import logger


class WebSocketStream:
    """Real-time стрим цен через WebSocket."""

    BASE_WS = "wss://stream.binance.com:9443/ws"

    def __init__(self):
        self.prices: Dict[str, float] = {}
        self.callbacks: list[Callable] = []
        self._running = False

    async def start(self, symbols: list[str]):
        """Запуск стрима."""
        streams = "/".join([f"{s.lower()}@ticker" for s in symbols])
        url = f"{self.BASE_WS}/{streams}"

        self._running = True
        logger.info(f"📡 WebSocket стрим запущен: {len(symbols)} пар")

        try:
            async with websockets.connect(url) as ws:
                while self._running:
                    msg = await ws.recv()
                    data = json.loads(msg)

                    if 's' in data:
                        symbol = data['s']
                        price = float(data['c'])
                        change = float(data['P'])
                        volume = float(data['v'])

                        self.prices[symbol] = {
                            'price': price,
                            'change_pct': change,
                            'volume': volume,
                        }

                        # Вызов колбэков
                        for cb in self.callbacks:
                            try:
                                cb(symbol, price, change, volume)
                            except Exception:
                                pass
        except Exception as e:
            logger.error(f"WebSocket ошибка: {e}")
            self._running = False

    def on_price_update(self, callback: Callable):
        """Подписка на обновления цен."""
        self.callbacks.append(callback)

    def get_price(self, symbol: str) -> float:
        """Текущая цена из стрима."""
        return self.prices.get(symbol, {}).get('price', 0)

    async def stop(self):
        self._running = False
        logger.info("📡 WebSocket стрим остановлен")