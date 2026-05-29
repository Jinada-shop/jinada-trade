"""
Файл: scanner.py
Сканер волатильных пар и heatmap рынка.
"""

import asyncio
from typing import Dict, List, Tuple

import pandas as pd

from config import config
from logger import logger


class MarketScanner:
    """Сканирует рынок на волатильность и объёмы."""

    def __init__(self, fetcher):
        self.fetcher = fetcher

    async def get_top_volatile(self, symbols: List[str], top_n: int = 30) -> List[str]:
        """Топ-N самых волатильных пар."""
        volatilities = []

        for symbol in symbols:
            df = await self.fetcher(symbol, "1h", 24)
            if not df.empty and len(df) >= 10:
                vol = df['close'].pct_change().std() * 100
                volume = df['volume'].iloc[-1]
                volatilities.append((symbol, vol, volume))

        volatilities.sort(key=lambda x: x[1], reverse=True)
        return [v[0] for v in volatilities[:top_n]]

    async def get_top_by_volume(self, symbols: List[str], top_n: int = 30) -> List[str]:
        """Топ-N по объёму."""
        volumes = []

        for symbol in symbols:
            df = await self.fetcher(symbol, "1h", 24)
            if not df.empty:
                avg_vol = df['volume'].mean()
                volumes.append((symbol, avg_vol))

        volumes.sort(key=lambda x: x[1], reverse=True)
        return [v[0] for v in volumes[:top_n]]

    async def get_heatmap(self, symbols: List[str]) -> Dict:
        """Heatmap рынка: % изменения за 1ч и 24ч."""
        heatmap = []

        for symbol in symbols:
            df = await self.fetcher(symbol, "1h", 25)
            if not df.empty and len(df) >= 24:
                change_1h = (df['close'].iloc[-1] / df['close'].iloc[-2] - 1) * 100
                change_24h = (df['close'].iloc[-1] / df['close'].iloc[-24] - 1) * 100
                heatmap.append({
                    'symbol': symbol,
                    'change_1h': round(change_1h, 2),
                    'change_24h': round(change_24h, 2),
                    'price': df['close'].iloc[-1],
                })

        heatmap.sort(key=lambda x: x['change_1h'], reverse=True)

        return {
            'top_gainers': [h for h in heatmap if h['change_1h'] > 0][:5],
            'top_losers': [h for h in heatmap if h['change_1h'] < 0][-5:],
            'all': heatmap[:20],
        }

    async def update_symbols(self, all_binance_symbols: List[str]) -> List[str]:
        """Обновить список отслеживаемых пар."""
        # Берём топ по волатильности + топ по объёму
        volatile = await self.get_top_volatile(all_binance_symbols, 25)
        volume = await self.get_top_by_volume(all_binance_symbols, 25)

        # Объединяем без дубликатов
        combined = list(dict.fromkeys(volatile + volume))[:45]

        logger.info(f"🔄 Обновлено пар: {len(combined)} (волатильность + объём)")
        return combined