"""
Файл: smart_exit.py
"""

from datetime import datetime
from typing import Dict, Tuple

import pandas as pd

from config import config


class SmartExit:
    def check(self, position: Dict, current_price: float,
              df: pd.DataFrame) -> Tuple[bool, str, str, float]:
        if df.empty or len(df) < 20:
            return False, "", "hold", 0

        last = df.iloc[-1]
        entry = position['price']
        pos_type = position['type']

        if pos_type == 'BUY':
            pnl_pct = (current_price - entry) / entry * 100
        else:
            pnl_pct = (entry - current_price) / entry * 100

        if pnl_pct <= -0.5:
            return True, f"Стоп-лосс ({pnl_pct:.1f}%)", "close_all", 100

        if pnl_pct >= 0.3 and not position.get('breakeven_done'):
            position['breakeven_done'] = True
            if pos_type == 'BUY':
                position['stop_loss'] = entry * 1.001
            else:
                position['stop_loss'] = entry * 0.999
            return True, f"Безубыток (+{pnl_pct:.1f}%)", "close_partial", 20

        if pnl_pct >= 1.0 and not position.get('indicator_exit_done'):
            rsi = last.get('RSI', 50)
            macd = last.get('MACD', 0)
            macd_signal = last.get('MACD_signal', 0)

            if (pos_type == 'BUY' and rsi > 70) or (pos_type == 'SELL' and rsi < 30):
                position['indicator_exit_done'] = True
                return True, f"RSI экстремум ({rsi:.0f})", "close_partial", 30

            prev_macd = df['MACD'].iloc[-2] if len(df) >= 2 else macd
            prev_signal = df['MACD_signal'].iloc[-2] if len(df) >= 2 else macd_signal

            if pos_type == 'BUY' and prev_macd > prev_signal and macd <= macd_signal:
                position['indicator_exit_done'] = True
                return True, "MACD вниз", "close_partial", 30

            if pos_type == 'SELL' and prev_macd < prev_signal and macd >= macd_signal:
                position['indicator_exit_done'] = True
                return True, "MACD вверх", "close_partial", 30

        if pnl_pct >= 2.0:
            atr = last.get('ATR', current_price * 0.01)
            if pos_type == 'BUY':
                new_stop = current_price - atr * 1.5
                if new_stop > position.get('stop_loss', 0):
                    position['stop_loss'] = new_stop
            else:
                new_stop = current_price + atr * 1.5
                if new_stop < position.get('stop_loss', float('inf')):
                    position['stop_loss'] = new_stop

        if pos_type == 'BUY' and current_price <= position.get('stop_loss', 0):
            return True, f"Трейлинг-стоп ({pnl_pct:.1f}%)", "close_remaining", 100
        if pos_type == 'SELL' and current_price >= position.get('stop_loss', float('inf')):
            return True, f"Трейлинг-стоп ({pnl_pct:.1f}%)", "close_remaining", 100

        if 'entry_time' in position:
            hours = (datetime.now() - position['entry_time']).total_seconds() / 3600
            if hours > config.MAX_POSITION_HOURS:
                return True, f"Таймаут ({hours:.0f}ч)", "close_all", 100

        return False, "", "hold", 0

    def get_plan(self, entry_price: float, position_type: str) -> str:
        if position_type == 'BUY':
            return (
                "УМНЫЙ ВЫХОД:\n"
                "------------------------\n"
                f"Стоп: {entry_price * 0.995:.2f} (-0.5%)\n"
                f"1. Безубыток: {entry_price * 1.003:.2f} (+0.3%)\n"
                "2. RSI > 70 / MACD down\n"
                "3. Трейлинг ATR\n"
            )
        else:
            return (
                "УМНЫЙ ВЫХОД:\n"
                "------------------------\n"
                f"Стоп: {entry_price * 1.005:.2f} (-0.5%)\n"
                f"1. Безубыток: {entry_price * 0.997:.2f} (+0.3%)\n"
                "2. RSI < 30 / MACD up\n"
                "3. Трейлинг ATR\n"
            )