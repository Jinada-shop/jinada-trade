"""
Файл: smart_trader.py
Умный вход и выход из позиций.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import config
from logger import logger


class SmartEntry:
    """
    Умный вход в позицию.
    
    Правила:
    1. Ждать откат к EMA9 (лучшая цена)
    2. Входить частями (50% сейчас, 50% при -0.5%)
    3. Проверять объём (выше среднего = надёжнее)
    4. Проверять спред (низкий = ликвидный рынок)
    5. Учитывать время (не входить в низколиквидные часы)
    """

    def __init__(self, exchange_client):
        self.exchange = exchange_client

    def should_enter(self, signal: Dict, df: pd.DataFrame, 
                    orderbook: Dict = None) -> Tuple[bool, str, float]:
        """
        Проверка: стоит ли входить прямо сейчас.
        
        Возвращает: (входить?, причина, лучшая_цена)
        """
        if df.empty or len(df) < 20:
            return False, "Недостаточно данных", 0

        last = df.iloc[-1]
        current_price = signal.get('price', last['close'])
        signal_type = signal.get('type', 'BUY')

        # === 1. ОТКАТ К EMA ===
        ema9 = last.get('EMA9', current_price)
        ema21 = last.get('EMA21', current_price)
        
        if signal_type == 'BUY':
            # Ждём цену у EMA9 (откат)
            distance_to_ema = (current_price - ema9) / ema9 * 100
            if distance_to_ema > 1.0:
                # Цена далеко от EMA — ждём откат
                best_price = ema9 * 0.998  # Чуть ниже EMA
                return False, f"Жду откат к EMA9 (сейчас +{distance_to_ema:.1f}%)", best_price
            elif distance_to_ema < -0.5:
                # Цена ниже EMA — хороший вход
                best_price = current_price
                # Проверяем не падает ли дальше
                if last['close'] < last['EMA21']:
                    return False, "Цена ниже EMA21 — тренд слабый", current_price
            else:
                best_price = current_price
        else:
            distance_to_ema = (ema9 - current_price) / current_price * 100
            if distance_to_ema > 1.0:
                best_price = ema9 * 1.002
                return False, f"Жду откат к EMA9 (сейчас +{distance_to_ema:.1f}%)", best_price
            elif distance_to_ema < -0.5:
                best_price = current_price
                if last['close'] > last['EMA21']:
                    return False, "Цена выше EMA21 — тренд слабый", current_price
            else:
                best_price = current_price

        # === 2. ПРОВЕРКА ОБЪЁМА ===
        volume_ratio = last.get('volume_ratio', 1)
        if volume_ratio < 0.8:
            return False, f"Объём ниже среднего (x{volume_ratio:.1f})", best_price

        # === 3. ПРОВЕРКА СПРЕДА ===
        if orderbook:
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            if bids and asks:
                spread = (asks[0][0] - bids[0][0]) / bids[0][0] * 100
                if spread > 0.15:
                    return False, f"Спред высокий ({spread:.2f}%)", best_price

        # === 4. ПРОВЕРКА ВРЕМЕНИ ===
        hour = datetime.now().hour
        if 2 <= hour < 6:
            # Ночью только сильные сигналы
            if signal.get('ai_score', 0) < 0.65:
                return False, "Ночное время — нужен STRONG сигнал", best_price

        # === 5. ПРОВЕРКА RSI ===
        rsi = last.get('RSI', 50)
        if signal_type == 'BUY' and rsi > 60:
            return False, f"RSI высокий ({rsi:.0f}) — жду коррекцию", best_price
        if signal_type == 'SELL' and rsi < 40:
            return False, f"RSI низкий ({rsi:.0f}) — жду коррекцию", best_price

        # === 6. ПРОВЕРКА MACD ===
        macd = last.get('MACD', 0)
        macd_signal = last.get('MACD_signal', 0)
        if signal_type == 'BUY' and macd < macd_signal:
            return False, "MACD медвежий", best_price
        if signal_type == 'SELL' and macd > macd_signal:
            return False, "MACD бычий", best_price

        # === 7. ПРОВЕРКА ADX (сила тренда) ===
        adx = last.get('ADX', 20)
        if adx < 15:
            return False, f"Нет тренда (ADX={adx:.0f})", best_price

        # ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ
        return True, "Все условия выполнены", best_price

    def calculate_entry_prices(self, base_price: float, signal_type: str) -> List[Dict]:
        """
        Расчёт сетки входа (3 уровня).
        BUY: 100% сейчас, 50% при -0.5%, 50% при -1%
        SELL: 100% сейчас, 50% при +0.5%, 50% при +1%
        """
        levels = []
        
        if signal_type == 'BUY':
            levels = [
                {'price': base_price, 'size_pct': 100, 'reason': 'Основной вход'},
                {'price': base_price * 0.995, 'size_pct': 50, 'reason': 'Откат -0.5%'},
                {'price': base_price * 0.99, 'size_pct': 50, 'reason': 'Откат -1.0%'},
            ]
        else:
            levels = [
                {'price': base_price, 'size_pct': 100, 'reason': 'Основной вход'},
                {'price': base_price * 1.005, 'size_pct': 50, 'reason': 'Рост +0.5%'},
                {'price': base_price * 1.01, 'size_pct': 50, 'reason': 'Рост +1.0%'},
            ]
        
        return levels


class SmartExit:
    """
    Умный выход из позиции.
    
    Правила:
    1. Частичный тейк на +1.5% (50% позиции)
    2. Стоп в безубыток при +1%
    3. Трейлинг-стоп по EMA9
    4. Выход при слабости (ADX падает)
    5. Выход при дивергенции RSI
    6. Выход по времени (висит > 4ч без движения)
    """

    def __init__(self):
        self.positions_exit_data: Dict[str, Dict] = {}

    def should_exit(self, position: Dict, current_price: float, 
                   df: pd.DataFrame) -> Tuple[bool, str, str]:
        """
        Проверка: пора ли закрывать позицию.
        
        Возвращает: (закрывать?, причина, какое_действие)
        """
        if df.empty or len(df) < 20:
            return False, "", "hold"

        last = df.iloc[-1]
        entry = position['price']
        pos_type = position['type']
        pos_id = position.get('order_id', 'unknown')

        # Расчёт PnL
        if pos_type == 'BUY':
            pnl_pct = (current_price - entry) / entry * 100
        else:
            pnl_pct = (entry - current_price) / entry * 100

        # === 1. ЧАСТИЧНЫЙ ТЕЙК ===
        if pnl_pct >= 1.5 and not position.get('partial_closed'):
            return True, f"Частичный тейк +{pnl_pct:.1f}%", "close_50%"

        # === 2. СТОП В БЕЗУБЫТОК ===
        if pnl_pct >= 1.0 and position.get('stop_loss', 0) < entry:
            new_stop = entry * 1.001 if pos_type == 'BUY' else entry * 0.999
            position['stop_loss'] = new_stop
            position['breakeven_activated'] = True
            return False, f"Стоп в безубыток (+{pnl_pct:.1f}%)", "update_stop"

        # === 3. ТРЕЙЛИНГ-СТОП ПО EMA ===
        ema9 = last.get('EMA9', current_price)
        if pnl_pct >= 2.0:
            if pos_type == 'BUY':
                new_stop = ema9 * 0.998
                if new_stop > position.get('stop_loss', 0):
                    position['stop_loss'] = new_stop
                    return False, f"Трейлинг по EMA9 (+{pnl_pct:.1f}%)", "update_stop"
            else:
                new_stop = ema9 * 1.002
                if new_stop < position.get('stop_loss', float('inf')):
                    position['stop_loss'] = new_stop
                    return False, f"Трейлинг по EMA9 (+{pnl_pct:.1f}%)", "update_stop"

        # === 4. ВЫХОД ПРИ СЛАБОСТИ ===
        adx = last.get('ADX', 25)
        if adx < 15 and pnl_pct > 0:
            return True, f"Тренд ослаб (ADX={adx:.0f})", "close_all"

        # === 5. ДИВЕРГЕНЦИЯ RSI ===
        if 'RSI' in df.columns and len(df) >= 10:
            rsi_now = last['RSI']
            rsi_prev = df['RSI'].iloc[-10]
            price_now = last['close']
            price_prev = df['close'].iloc[-10]
            
            # Медвежья дивергенция (цена выше, RSI ниже)
            if price_now > price_prev and rsi_now < rsi_prev and pos_type == 'BUY':
                return True, "Медвежья дивергенция RSI", "close_all"
            
            # Бычья дивергенция (цена ниже, RSI выше)
            if price_now < price_prev and rsi_now > rsi_prev and pos_type == 'SELL':
                return True, "Бычья дивергенция RSI", "close_all"

        # === 6. ВЫХОД ПО ВРЕМЕНИ ===
        if 'entry_time' in position:
            hours_open = (datetime.now() - position['entry_time']).total_seconds() / 3600
            if hours_open > 4 and abs(pnl_pct) < 0.3:
                return True, f"Висит {hours_open:.0f}ч без движения", "close_all"

        # === 7. СТОП-ЛОСС ===
        if pos_type == 'BUY':
            if current_price <= position.get('stop_loss', 0):
                return True, f"Стоп-лосс ({position['stop_loss']})", "close_all"
        else:
            if current_price >= position.get('stop_loss', float('inf')):
                return True, f"Стоп-лосс ({position['stop_loss']})", "close_all"

        # === 8. ТЕЙК-ПРОФИТ ===
        if pos_type == 'BUY':
            if current_price >= position.get('take_profit', float('inf')):
                return True, "Тейк-профит", "close_all"
        else:
            if current_price <= position.get('take_profit', 0):
                return True, "Тейк-профит", "close_all"

        return False, "", "hold"

    def calculate_exit_levels(self, entry_price: float, position_type: str) -> Dict:
        """Расчёт уровней выхода."""
        if position_type == 'BUY':
            return {
                'partial_take': entry_price * 1.015,    # +1.5%
                'breakeven': entry_price * 1.001,        # Безубыток
                'trailing_ema': None,                     # Динамический
                'full_take': entry_price * 1.03,         # +3%
                'stop_loss': entry_price * 0.99,         # -1%
            }
        else:
            return {
                'partial_take': entry_price * 0.985,    # +1.5%
                'breakeven': entry_price * 0.999,        # Безубыток
                'trailing_ema': None,
                'full_take': entry_price * 0.97,         # +3%
                'stop_loss': entry_price * 1.01,         # -1%
            }