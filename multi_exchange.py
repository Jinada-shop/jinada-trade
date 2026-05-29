"""
Файл: multi_exchange.py
Мульти-биржа: Binance + Bybit.
"""

import asyncio
from typing import Dict, Optional

import pandas as pd

from binance_client import exchange as binance_ex
from bybit_client import BybitClient
from config import config
from logger import logger


class MultiExchange:
    """Объединяет Binance и Bybit."""
    
    def __init__(self):
        self.binance = binance_ex
        self.bybit = BybitClient(
            api_key=getattr(config, 'BYBIT_API_KEY', ''),
            api_secret=getattr(config, 'BYBIT_SECRET_KEY', ''),
        )
        self.primary = "binance"
    
    async def initialize(self):
        await self.binance.initialize()
        await self.bybit.initialize()
        logger.info("✅ Мульти-биржа готова (Binance + Bybit)")
    
    async def get_current_price(self, symbol: str, exchange: str = None) -> Optional[float]:
        exchange = exchange or self.primary
        
        if exchange == "binance":
            return await self.binance.get_current_price(symbol)
        elif exchange == "bybit":
            return await self.bybit.get_current_price(symbol)
        return None
    
    async def get_best_price(self, symbol: str, side: str = "BUY") -> Dict:
        """Найти лучшую цену среди бирж."""
        prices = {}
        
        binance_price = await self.binance.get_current_price(symbol)
        if binance_price:
            prices["binance"] = binance_price
        
        bybit_price = await self.bybit.get_current_price(symbol)
        if bybit_price:
            prices["bybit"] = bybit_price
        
        if not prices:
            return {"exchange": None, "price": 0}
        
        if side == "BUY":
            best = min(prices.items(), key=lambda x: x[1])
        else:
            best = max(prices.items(), key=lambda x: x[1])
        
        return {"exchange": best[0], "price": best[1], "all_prices": prices}
    
    async def get_klines(self, symbol: str, interval: str = "15m", limit: int = 200,
                        exchange: str = None) -> pd.DataFrame:
        exchange = exchange or self.primary
        
        if exchange == "binance":
            return await self.binance.get_klines(symbol, interval, limit)
        elif exchange == "bybit":
            return await self.bybit.get_klines(symbol, interval, limit)
        return pd.DataFrame()
    
    async def create_order(self, symbol: str, side: str, quantity: float,
                          exchange: str = None) -> Optional[Dict]:
        exchange = exchange or self.primary
        
        if exchange == "binance":
            return await self.binance.create_market_order(symbol, side, quantity)
        elif exchange == "bybit":
            return await self.bybit.create_market_order(symbol, side, quantity)
        return None
    
    async def get_total_balance(self) -> Dict[str, float]:
        """Общий баланс по всем биржам."""
        total = {"USDT": 0}
        
        binance_bal = await self.binance.get_balance()
        for asset, amount in binance_bal.items():
            total[asset] = total.get(asset, 0) + amount
        
        bybit_bal = await self.bybit.get_balance()
        for asset, amount in bybit_bal.items():
            total[asset] = total.get(asset, 0) + amount
        
        return total
    
    async def find_arbitrage(self, symbol: str) -> Dict:
        """Поиск арбитража между биржами."""
        binance_price = await self.binance.get_current_price(symbol)
        bybit_price = await self.bybit.get_current_price(symbol)
        
        if binance_price and bybit_price:
            spread = (bybit_price - binance_price) / binance_price * 100
            return {
                "symbol": symbol,
                "binance": binance_price,
                "bybit": bybit_price,
                "spread_pct": round(spread, 3),
                "opportunity": abs(spread) > 0.5,
            }
        return {}
    
    async def close(self):
        if hasattr(self.binance, 'close'):
            self.binance.close()
        if hasattr(self.bybit, 'close'):
            self.bybit.close()


# Глобальный экземпляр
multi_exchange = MultiExchange()