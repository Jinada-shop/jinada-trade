"""
Файл: strategies.py — ПРОДВИНУТЫЕ СТРАТЕГИИ
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

from indicators import Indicators


class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name
        self.indicators = Indicators()
    
    @abstractmethod
    def analyze(self, df: pd.DataFrame, symbol: str, timeframe: str = "15m") -> List[Dict]:
        pass
    
    def _signal(self, tp: str, sym: str, tf: str, last: pd.Series, reason: str, conf: float, **kwargs) -> Dict:
        body = abs(last.get('body', last['close'] - last['open']))
        lower_wick = last.get('lower_wick', min(last['open'], last['close']) - last['low'])
        wick_ratio = lower_wick / (body + 0.0001) if body > 0 else 0
        
        return {
            'type': tp, 'symbol': sym, 'strategy': self.name,
            'timeframe': tf, 'price': last['close'],
            'confidence': conf, 'rsi': last.get('RSI', 50),
            'volume_ratio': last.get('volume_ratio', 1),
            'atr': last.get('ATR', last['close'] * 0.01),
            'adx': last.get('ADX', 20),
            'macd': last.get('MACD', 0),
            'macd_signal': last.get('MACD_signal', 0),
            'body_pct': last.get('body_pct', 0),
            'wick_ratio': wick_ratio,
            'bb_width': last.get('BB_width', 0.02),
            'momentum': last.get('momentum', 0),
            'atr_pct': last.get('ATR_pct', 1),
            'ema_distance_9': (last['close'] - last.get('EMA9', last['close'])) / last.get('EMA9', last['close']) * 100,
            'ema_distance_21': (last['close'] - last.get('EMA21', last['close'])) / last.get('EMA21', last['close']) * 100,
            'ema_distance_50': (last['close'] - last.get('EMA50', last['close'])) / last.get('EMA50', last['close']) * 100,
            'reason': reason,
            **kwargs,
        }


# ======================================================================
class ScalpingStrategy(BaseStrategy):
    """Продвинутый скальпинг: пробои BB + паттерны + дивергенции."""
    
    def __init__(self):
        super().__init__("scalping")
    
    def _detect_divergence(self, df: pd.DataFrame, direction: str = 'bullish') -> bool:
        """Поиск дивергенций RSI."""
        if len(df) < 20:
            return False
        
        last_5 = df.iloc[-5:]
        last_10 = df.iloc[-10:-5]
        
        if direction == 'bullish':
            # Цена ниже, RSI выше
            price_lower = last_5['close'].min() < last_10['close'].min()
            rsi_higher = last_5['RSI'].min() > last_10['RSI'].min()
            return price_lower and rsi_higher
        else:
            # Цена выше, RSI ниже
            price_higher = last_5['close'].max() > last_10['close'].max()
            rsi_lower = last_5['RSI'].max() < last_10['RSI'].max()
            return price_higher and rsi_lower
    
    def _is_hammer(self, row: pd.Series) -> bool:
        """Паттерн молот."""
        body = abs(row.get('body', row['close'] - row['open']))
        lower_wick = row.get('lower_wick', min(row['open'], row['close']) - row['low'])
        upper_wick = row.get('upper_wick', row['high'] - max(row['open'], row['close']))
        return (lower_wick > body * 2) and (upper_wick < body * 0.3) and body > 0
    
    def _is_shooting_star(self, row: pd.Series) -> bool:
        """Паттерн падающая звезда."""
        body = abs(row.get('body', row['close'] - row['open']))
        upper_wick = row.get('upper_wick', row['high'] - max(row['open'], row['close']))
        lower_wick = row.get('lower_wick', min(row['open'], row['close']) - row['low'])
        return (upper_wick > body * 2) and (lower_wick < body * 0.3) and body > 0
    
    def _is_engulfing(self, df: pd.DataFrame, direction: str = 'bullish') -> bool:
        """Паттерн поглощения."""
        if len(df) < 2:
            return False
        prev = df.iloc[-2]
        last = df.iloc[-1]
        
        if direction == 'bullish':
            return (prev['close'] < prev['open'] and 
                    last['close'] > last['open'] and
                    last['open'] <= prev['close'] and 
                    last['close'] >= prev['open'])
        else:
            return (prev['close'] > prev['open'] and 
                    last['close'] < last['open'] and
                    last['open'] >= prev['close'] and 
                    last['close'] <= prev['open'])
    
    def analyze(self, df: pd.DataFrame, symbol: str, timeframe: str = "15m") -> List[Dict]:
        df = self.indicators.add_all(df)
        if df.empty or len(df) < 50:
            return []
        
        signals = []
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # === СТАНДАРТНЫЙ ПРОБОЙ BB ===
        bb_breakout_up = (
            last['close'] > last['BB_upper'] and
            prev['close'] <= prev['BB_upper'] and
            last['volume_ratio'] > 1.3
        )
        
        bb_breakout_down = (
            last['close'] < last['BB_lower'] and
            prev['close'] >= prev['BB_lower'] and
            last['volume_ratio'] > 1.3
        )
        
        # === ПАТТЕРНЫ ===
        hammer = self._is_hammer(last)
        shooting_star = self._is_shooting_star(last)
        bullish_engulfing = self._is_engulfing(df, 'bullish')
        bearish_engulfing = self._is_engulfing(df, 'bearish')
        
        # === ДИВЕРГЕНЦИИ ===
        bullish_div = self._detect_divergence(df, 'bullish')
        bearish_div = self._detect_divergence(df, 'bearish')
        
        # === КОМБИНИРОВАННЫЕ СИГНАЛЫ BUY ===
        buy_score = 0
        buy_reasons = []
        
        if bb_breakout_up:
            buy_score += 3
            buy_reasons.append("BB пробой вверх")
        if hammer:
            buy_score += 2
            buy_reasons.append("Молот")
        if bullish_engulfing:
            buy_score += 2
            buy_reasons.append("Бычье поглощение")
        if bullish_div:
            buy_score += 3
            buy_reasons.append("Бычья дивергенция RSI")
        if last['RSI'] < 40:
            buy_score += 1
            buy_reasons.append(f"RSI={last['RSI']:.0f}")
        if last['volume_ratio'] > 2.0:
            buy_score += 1
            buy_reasons.append(f"Объём x{last['volume_ratio']:.1f}")
        if last['ADX'] > 25 and last.get('plus_DI', 0) > last.get('minus_DI', 0):
            buy_score += 1
            buy_reasons.append("ADX+DI вверх")
        
        if buy_score >= 4:
            confidence = min(0.95, 0.40 + buy_score * 0.08)
            signals.append(self._signal('BUY', symbol, timeframe, last,
                " + ".join(buy_reasons), confidence))
        
        # === КОМБИНИРОВАННЫЕ СИГНАЛЫ SELL ===
        sell_score = 0
        sell_reasons = []
        
        if bb_breakout_down:
            sell_score += 3
            sell_reasons.append("BB пробой вниз")
        if shooting_star:
            sell_score += 2
            sell_reasons.append("Падающая звезда")
        if bearish_engulfing:
            sell_score += 2
            sell_reasons.append("Медвежье поглощение")
        if bearish_div:
            sell_score += 3
            sell_reasons.append("Медвежья дивергенция RSI")
        if last['RSI'] > 60:
            sell_score += 1
            sell_reasons.append(f"RSI={last['RSI']:.0f}")
        if last['volume_ratio'] > 2.0:
            sell_score += 1
            sell_reasons.append(f"Объём x{last['volume_ratio']:.1f}")
        if last['ADX'] > 25 and last.get('minus_DI', 0) > last.get('plus_DI', 0):
            sell_score += 1
            sell_reasons.append("ADX-DI вниз")
        
        if sell_score >= 4:
            confidence = min(0.95, 0.40 + sell_score * 0.08)
            signals.append(self._signal('SELL', symbol, timeframe, last,
                " + ".join(sell_reasons), confidence))
        
        return signals


# ======================================================================
class TrendStrategy(BaseStrategy):
    """Продвинутый трендовый трейдинг: EMA-каскад + VWAP + SuperTrend."""
    
    def __init__(self):
        super().__init__("trend")
    
    def _supertrend(self, df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
        """Индикатор SuperTrend."""
        high, low, close = df['high'], df['low'], df['close']
        
        atr = Indicators.atr(df, period)
        hl2 = (high + low) / 2
        
        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)
        
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)
        
        direction.iloc[0] = 1 if close.iloc[0] > upper_band.iloc[0] else -1
        
        for i in range(1, len(df)):
            if close.iloc[i] > upper_band.iloc[i-1]:
                direction.iloc[i] = 1
            elif close.iloc[i] < lower_band.iloc[i-1]:
                direction.iloc[i] = -1
            else:
                direction.iloc[i] = direction.iloc[i-1]
            
            if direction.iloc[i] == 1:
                supertrend.iloc[i] = lower_band.iloc[i]
            else:
                supertrend.iloc[i] = upper_band.iloc[i]
        
        return pd.DataFrame({'supertrend': supertrend, 'direction': direction})
    
    def _ema_score(self, row: pd.Series) -> Tuple[int, str]:
        """Оценка EMA-каскада."""
        price = row['close']
        ema9 = row.get('EMA9', price)
        ema21 = row.get('EMA21', price)
        ema50 = row.get('EMA50', price)
        ema200 = row.get('EMA200', price)
        
        # Бычьи каскады
        if price > ema9 > ema21 > ema50 > ema200:
            return 5, "Идеальный бычий каскад EMA"
        elif price > ema9 > ema21 > ema50:
            return 4, "Бычий каскад EMA (9>21>50)"
        elif price > ema21 > ema50:
            return 3, "Бычий EMA (цена>21>50)"
        # Медвежьи каскады
        elif price < ema9 < ema21 < ema50 < ema200:
            return -5, "Идеальный медвежий каскад EMA"
        elif price < ema9 < ema21 < ema50:
            return -4, "Медвежий каскад EMA (9<21<50)"
        elif price < ema21 < ema50:
            return -3, "Медвежий EMA (цена<21<50)"
        else:
            return 0, "Нет каскада EMA"
    
    def _calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        """Расчёт VWAP."""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
        return vwap
    
    def analyze(self, df: pd.DataFrame, symbol: str, timeframe: str = "1h") -> List[Dict]:
        df = self.indicators.add_all(df)
        if df.empty or len(df) < 50:
            return []
        
        signals = []
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # SuperTrend и VWAP
        try:
            st = self._supertrend(df)
            last_st_dir = st['direction'].iloc[-1] if not st.empty else 0
            prev_st_dir = st['direction'].iloc[-2] if len(st) > 1 else 0
        except Exception:
            last_st_dir = 0
            prev_st_dir = 0
        
        df['VWAP'] = self._calculate_vwap(df)
        last_vwap = df['VWAP'].iloc[-1]
        
        # EMA оценка
        ema_points, ema_reason = self._ema_score(last)
        
        # === СИГНАЛЫ BUY ===
        buy_score = 0
        buy_reasons = []
        
        if ema_points >= 3:
            buy_score += abs(ema_points)
            buy_reasons.append(ema_reason)
        
        if prev_st_dir == -1 and last_st_dir == 1:
            buy_score += 3
            buy_reasons.append("SuperTrend разворот вверх")
        elif last_st_dir == 1:
            buy_score += 1
        
        if last['close'] > last['EMA21']:
            distance = abs(last['close'] - last['EMA21']) / last['EMA21'] * 100
            if distance < 1.5 and last['RSI'] > 45:
                buy_score += 2
                buy_reasons.append(f"Откат к EMA21 ({distance:.1f}%)")
        
        if last['close'] > last_vwap and last['close'] / last_vwap < 1.02:
            buy_score += 2
            buy_reasons.append("Поддержка VWAP")
        
        if last['MACD'] > last['MACD_signal']:
            buy_score += 1
        if last['MACD_hist'] > 0 and prev['MACD_hist'] <= 0:
            buy_score += 2
            buy_reasons.append("MACD гистограмма стала положительной")
        
        if last['ADX'] > 30 and last.get('plus_DI', 0) > last.get('minus_DI', 0):
            buy_score += 2
            buy_reasons.append(f"Сильный тренд (ADX={last['ADX']:.0f})")
        
        if last['volume_ratio'] > 1.5:
            buy_score += 1
            buy_reasons.append(f"Объём x{last['volume_ratio']:.1f}")
        
        if buy_score >= 6:
            confidence = min(0.95, 0.45 + buy_score * 0.04)
            signals.append(self._signal('BUY', symbol, timeframe, last,
                " + ".join(buy_reasons), confidence,
                vwap=last_vwap, ema_score=ema_points))
        
        # === СИГНАЛЫ SELL ===
        sell_score = 0
        sell_reasons = []
        
        if ema_points <= -3:
            sell_score += abs(ema_points)
            sell_reasons.append(ema_reason)
        
        if prev_st_dir == 1 and last_st_dir == -1:
            sell_score += 3
            sell_reasons.append("SuperTrend разворот вниз")
        elif last_st_dir == -1:
            sell_score += 1
        
        if last['close'] < last['EMA21']:
            distance = abs(last['close'] - last['EMA21']) / last['EMA21'] * 100
            if distance < 1.5 and last['RSI'] < 55:
                sell_score += 2
                sell_reasons.append(f"Откат к EMA21 ({distance:.1f}%)")
        
        if last['close'] < last_vwap and last_vwap / last['close'] < 1.02:
            sell_score += 2
            sell_reasons.append("Сопротивление VWAP")
        
        if last['MACD'] < last['MACD_signal']:
            sell_score += 1
        if last['MACD_hist'] < 0 and prev['MACD_hist'] >= 0:
            sell_score += 2
            sell_reasons.append("MACD гистограмма стала отрицательной")
        
        if last['ADX'] > 30 and last.get('minus_DI', 0) > last.get('plus_DI', 0):
            sell_score += 2
            sell_reasons.append(f"Сильный тренд вниз (ADX={last['ADX']:.0f})")
        
        if last['volume_ratio'] > 1.5:
            sell_score += 1
            sell_reasons.append(f"Объём x{last['volume_ratio']:.1f}")
        
        if sell_score >= 6:
            confidence = min(0.95, 0.45 + sell_score * 0.04)
            signals.append(self._signal('SELL', symbol, timeframe, last,
                " + ".join(sell_reasons), confidence,
                vwap=last_vwap, ema_score=ema_points))
        
        return signals


# ======================================================================
class CounterTrendStrategy(BaseStrategy):
    """Продвинутый контр-тренд: уровни + RSI экстремумы + паттерны разворота."""
    
    def __init__(self):
        super().__init__("counter_trend")
        self.dbscan = DBSCAN(eps=0.008, min_samples=3)
    
    def _find_levels(self, df: pd.DataFrame) -> Tuple[List[float], List[float]]:
        """Поиск уровней поддержки/сопротивления."""
        window = 20
        highs, lows = [], []
        
        for i in range(window, len(df) - window):
            if df['high'].iloc[i] == df['high'].iloc[i-window:i+window].max():
                highs.append(df['high'].iloc[i])
            if df['low'].iloc[i] == df['low'].iloc[i-window:i+window].min():
                lows.append(df['low'].iloc[i])
        
        def cluster(arr: List[float]) -> List[float]:
            if len(arr) < 2:
                return arr
            X = np.array(arr).reshape(-1, 1)
            if len(X) < 3:
                return arr
            try:
                lbls = self.dbscan.fit_predict(X / np.mean(X))
                clustered = {}
                for v, l in zip(arr, lbls):
                    if l != -1:
                        clustered.setdefault(l, []).append(v)
                return sorted([np.mean(v) for v in clustered.values()])
            except Exception:
                return arr
        
        return cluster(lows), cluster(highs)
    
    def _is_pin_bar(self, row: pd.Series, direction: str = 'bullish') -> bool:
        """Пин-бар (длинная тень, маленькое тело)."""
        body = abs(row.get('body', row['close'] - row['open']))
        upper_wick = row.get('upper_wick', row['high'] - max(row['open'], row['close']))
        lower_wick = row.get('lower_wick', min(row['open'], row['close']) - row['low'])
        total = upper_wick + lower_wick + body
        
        if total == 0:
            return False
        
        if direction == 'bullish':
            return (lower_wick > body * 3 and 
                    upper_wick < body * 0.5 and
                    body / total < 0.3)
        else:
            return (upper_wick > body * 3 and 
                    lower_wick < body * 0.5 and
                    body / total < 0.3)
    
    def _rsi_extreme(self, row: pd.Series) -> Optional[str]:
        """Экстремальные значения RSI."""
        rsi = row.get('RSI', 50)
        if rsi < 25:
            return 'oversold_extreme'
        elif rsi < 35:
            return 'oversold'
        elif rsi > 75:
            return 'overbought_extreme'
        elif rsi > 65:
            return 'overbought'
        return None
    
    def _level_strength(self, price: float, levels: List[float]) -> int:
        """Сила уровня (сколько раз тестировался)."""
        strength = 0
        for level in levels:
            if abs(price - level) / price < 0.01:
                strength += 1
        return strength
    
    def analyze(self, df: pd.DataFrame, symbol: str, timeframe: str = "15m") -> List[Dict]:
        df = self.indicators.add_all(df)
        if df.empty or len(df) < 50:
            return []
        
        signals = []
        last = df.iloc[-1]
        supports, resistances = self._find_levels(df)
        price = last['close']
        
        near_support = max([s for s in supports if s < price], default=None)
        near_resistance = min([r for r in resistances if r > price], default=None)
        
        rsi_state = self._rsi_extreme(last)
        is_bullish_pin = self._is_pin_bar(last, 'bullish')
        is_bearish_pin = self._is_pin_bar(last, 'bearish')
        
        # === BUY ОТ ПОДДЕРЖКИ ===
        if near_support:
            dist_to_support = abs(price - near_support) / near_support * 100
            support_strength = self._level_strength(near_support, supports)
            
            buy_conditions = []
            buy_score = 0
            
            if dist_to_support < 1.0:
                buy_score += 3
                buy_conditions.append(f"Близко к поддержке ({dist_to_support:.1f}%)")
            
            if rsi_state in ['oversold', 'oversold_extreme']:
                buy_score += 2 + (1 if rsi_state == 'oversold_extreme' else 0)
                buy_conditions.append(f"RSI={last['RSI']:.0f} ({rsi_state})")
            
            if is_bullish_pin:
                buy_score += 3
                buy_conditions.append("Бычий пин-бар")
            
            if last['volume_ratio'] > 1.5:
                buy_score += 1
                buy_conditions.append(f"Объём x{last['volume_ratio']:.1f}")
            
            if last['MACD_hist'] < 0 and last['MACD_hist'] > df['MACD_hist'].iloc[-2]:
                buy_score += 1
                buy_conditions.append("MACD разворот вверх")
            
            if buy_score >= 4:
                confidence = min(0.90, 0.35 + buy_score * 0.10)
                signals.append(self._signal('BUY', symbol, timeframe, last,
                    " + ".join(buy_conditions), confidence,
                    stop_loss=near_support * 0.995,
                    take_profit=near_resistance if near_resistance else price * 1.03,
                    support_strength=support_strength))
        
        # === SELL ОТ СОПРОТИВЛЕНИЯ ===
        if near_resistance:
            dist_to_resistance = abs(price - near_resistance) / near_resistance * 100
            resistance_strength = self._level_strength(near_resistance, resistances)
            
            sell_conditions = []
            sell_score = 0
            
            if dist_to_resistance < 1.0:
                sell_score += 3
                sell_conditions.append(f"Близко к сопротивлению ({dist_to_resistance:.1f}%)")
            
            if rsi_state in ['overbought', 'overbought_extreme']:
                sell_score += 2 + (1 if rsi_state == 'overbought_extreme' else 0)
                sell_conditions.append(f"RSI={last['RSI']:.0f} ({rsi_state})")
            
            if is_bearish_pin:
                sell_score += 3
                sell_conditions.append("Медвежий пин-бар")
            
            if last['volume_ratio'] > 1.5:
                sell_score += 1
                sell_conditions.append(f"Объём x{last['volume_ratio']:.1f}")
            
            if last['MACD_hist'] > 0 and last['MACD_hist'] < df['MACD_hist'].iloc[-2]:
                sell_score += 1
                sell_conditions.append("MACD разворот вниз")
            
            if sell_score >= 4:
                confidence = min(0.90, 0.35 + sell_score * 0.10)
                signals.append(self._signal('SELL', symbol, timeframe, last,
                    " + ".join(sell_conditions), confidence,
                    stop_loss=near_resistance * 1.005,
                    take_profit=near_support if near_support else price * 0.97,
                    resistance_strength=resistance_strength))
        
        return signals


# ======================================================================
class GridStrategy(BaseStrategy):
    """Новая стратегия: грид-трейдинг в боковике."""
    
    def __init__(self):
        super().__init__("grid")
    
    def analyze(self, df: pd.DataFrame, symbol: str, timeframe: str = "1h") -> List[Dict]:
        df = self.indicators.add_all(df)
        if df.empty or len(df) < 50:
            return []
        
        signals = []
        last = df.iloc[-1]
        
        bb_width = last.get('BB_width', 0.05)
        adx = last.get('ADX', 20)
        is_ranging = bb_width < 0.03 and adx < 20
        
        if not is_ranging:
            return []
        
        if last['close'] < last['BB_lower'] * 1.002 and last['RSI'] < 35:
            signals.append(self._signal('BUY', symbol, timeframe, last,
                f"Грид: нижняя граница (RSI={last['RSI']:.0f}, ADX={adx:.0f})",
                confidence=0.60,
                grid_level='lower'))
        
        if last['close'] > last['BB_upper'] * 0.998 and last['RSI'] > 65:
            signals.append(self._signal('SELL', symbol, timeframe, last,
                f"Грид: верхняя граница (RSI={last['RSI']:.0f}, ADX={adx:.0f})",
                confidence=0.60,
                grid_level='upper'))
        
        return signals