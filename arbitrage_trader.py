"""
Файл: arbitrage_trader.py
Автоматический межбиржевой арбитраж.
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional

from config import config
from logger import logger


class ArbitrageTrader:
    """
    Арбитраж между Binance и Bybit.
    
    Не требует перевода денег!
    Деньги должны быть на обеих биржах заранее.
    """
    
    def __init__(self, exchange_client):
        self.exchange = exchange_client
        self.min_spread = 0.5  # Минимальный спред для арбитража (%)
        self.max_position_usdt = 50.0  # Максимум на одну арбитражную сделку
        self.active_arbitrages: Dict[str, Dict] = {}
    
    async def scan_opportunity(self, symbol: str) -> Optional[Dict]:
        """Поиск арбитражной возможности."""
        # Получаем цены с двух бирж
        binance_price = await self.exchange.binance.get_current_price(symbol)
        bybit_price = await self.exchange.bybit.get_current_price(symbol)
        
        if not binance_price or not bybit_price:
            return None
        
        spread = (bybit_price - binance_price) / binance_price * 100
        
        # Проверяем что спред достаточный
        if abs(spread) < self.min_spread:
            return None
        
        # Определяем где покупать, где продавать
        if spread > 0:
            # Bybit дороже → покупаем на Binance, продаём на Bybit
            return {
                'symbol': symbol,
                'buy_exchange': 'binance',
                'sell_exchange': 'bybit',
                'buy_price': binance_price,
                'sell_price': bybit_price,
                'spread_pct': round(spread, 3),
                'profit_pct': round(spread - 0.2, 3),  # Минус комиссии ~0.2%
                'timestamp': datetime.now(),
            }
        else:
            # Binance дороже → покупаем на Bybit, продаём на Binance
            return {
                'symbol': symbol,
                'buy_exchange': 'bybit',
                'sell_exchange': 'binance',
                'buy_price': bybit_price,
                'sell_price': binance_price,
                'spread_pct': round(abs(spread), 3),
                'profit_pct': round(abs(spread) - 0.2, 3),
                'timestamp': datetime.now(),
            }
    
    async def execute_arbitrage(self, opportunity: Dict) -> bool:
        """Исполнить арбитражную сделку."""
        symbol = opportunity['symbol']
        
        # Проверяем что нет активного арбитража по этой паре
        if symbol in self.active_arbitrages:
            return False
        
        buy_ex = opportunity['buy_exchange']
        sell_ex = opportunity['sell_exchange']
        buy_price = opportunity['buy_price']
        sell_price = opportunity['sell_price']
        
        # Размер позиции
        usdt_amount = min(self.max_position_usdt, 50)
        quantity = usdt_amount / buy_price
        
        logger.info(f"🔁 АРБИТРАЖ: {symbol}")
        logger.info(f"   Покупка на {buy_ex}: {quantity:.6f} @ {buy_price}")
        logger.info(f"   Продажа на {sell_ex}: {quantity:.6f} @ {sell_price}")
        logger.info(f"   Ожидаемая прибыль: {opportunity['profit_pct']}%")
        
        # Покупаем на дешёвой бирже
        buy_order = await self.exchange.create_order(
            symbol=symbol,
            side='BUY',
            quantity=quantity,
            exchange=buy_ex,
        )
        
        if not buy_order:
            logger.error("❌ Ошибка покупки")
            return False
        
        # Продаём на дорогой бирже
        sell_order = await self.exchange.create_order(
            symbol=symbol,
            side='SELL',
            quantity=quantity,
            exchange=sell_ex,
        )
        
        if not sell_order:
            logger.error("❌ Ошибка продажи")
            # Нужно закрыть купленную позицию
            await self.exchange.create_order(
                symbol=symbol, side='SELL',
                quantity=quantity, exchange=buy_ex,
            )
            return False
        
        # Сохраняем арбитраж
        self.active_arbitrages[symbol] = {
            **opportunity,
            'quantity': quantity,
            'entry_time': datetime.now(),
        }
        
        profit_usdt = quantity * (sell_price - buy_price) * 0.998  # Минус комиссия
        logger.info(f"✅ АРБИТРАЖ УСПЕШЕН! Прибыль: +{profit_usdt:.2f}$")
        
        return True
    
    async def scan_all_pairs(self):
        """Сканирование всех пар на арбитраж."""
        opportunities = []
        
        for symbol in config.SYMBOLS[:5]:  # Топ-5 пар
            opp = await self.scan_opportunity(symbol)
            if opp and opp['profit_pct'] > 0.3:  # Минимальная прибыль после комиссий
                opportunities.append(opp)
        
        # Сортируем по прибыльности
        opportunities.sort(key=lambda x: x['profit_pct'], reverse=True)
        
        # Исполняем лучшую
        if opportunities:
            best = opportunities[0]
            logger.info(f"🔍 Лучший арбитраж: {best['symbol']} | Спред: {best['spread_pct']}% | Прибыль: {best['profit_pct']}%")
            
            if config.AUTO_TRADE and not config.PAPER_TRADING:
                await self.execute_arbitrage(best)
            else:
                logger.info(f"[PAPER] Арбитраж {best['symbol']}: +{best['profit_pct']}%")
        
        return opportunities
    
    def get_stats(self) -> str:
        """Статистика арбитража."""
        if not self.active_arbitrages:
            return "Нет активных арбитражей"
        
        text = "АКТИВНЫЕ АРБИТРАЖИ:\n"
        for sym, data in self.active_arbitrages.items():
            text += f"  {sym}: куплен на {data['buy_exchange']}, продан на {data['sell_exchange']} | +{data['profit_pct']}%\n"
        return text