"""
Файл: price_predictor.py — ГЛУБОКОЕ ПРОГНОЗИРОВАНИЕ ЦЕН
Обучается на истории 500-1000 часов для каждой пары
"""

import pickle
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from config import config
from database import get_db
from logger import logger


class PricePredictor:
    """
    Прогнозирует цену для каждой пары на основе глубокого обучения.
    
    Особенности:
    - Отдельная модель для каждой пары
    - Прогноз на 1ч, 4ч, 12ч, 24ч
    - Уверенность прогноза
    - Авто-переобучение
    """

    def __init__(self, fetcher=None):
        self.fetcher = fetcher
        self.models: Dict[str, Dict] = {}  # symbol -> {model, scaler, accuracy, features}
        self.last_train_time: Dict[str, datetime] = {}
        self.predictions: Dict[str, Dict] = {}  # Текущие прогнозы
        self.is_trained = False
        self._load()

    async def train_all_pairs(self, symbols: list = None, history_hours: int = 500):
        """Обучение моделей для всех пар."""
        if symbols is None:
            symbols = config.SYMBOLS

        logger.info("=" * 60)
        logger.info(f"🧠 ГЛУБОКОЕ ОБУЧЕНИЕ ДЛЯ {len(symbols)} ПАР")
        logger.info(f"📊 История: {history_hours} часов на пару")
        logger.info("=" * 60)

        trained = 0
        for symbol in symbols:
            try:
                success = await self.train_single_pair(symbol, history_hours)
                if success:
                    trained += 1
            except Exception as e:
                logger.error(f"  ❌ {symbol}: ошибка обучения — {e}")

        if trained > 0:
            self.is_trained = True
            self._save()
            logger.info(f"✅ Обучено {trained}/{len(symbols)} пар")
        else:
            logger.error("❌ Ни одна модель не обучена!")

    async def train_single_pair(self, symbol: str, history_hours: int = 500) -> bool:
        """
        Обучение модели для ОДНОЙ пары.
        
        Использует:
        - Технические индикаторы (RSI, MACD, BB, EMA, объёмы)
        - Паттерны свечей
        - Временные признаки (час, день недели)
        - Лаговые признаки (цена N свечей назад)
        """
        try:
            # Загружаем историю
            df = await self.fetcher(symbol, "15m", history_hours * 4)
            
            if df.empty or len(df) < 100:
                logger.warning(f"  {symbol}: мало данных ({len(df)} свечей)")
                return False

            # Добавляем все индикаторы
            from indicators import Indicators
            df = Indicators.add_all(df)

            # Создаём обучающие примеры
            X, y_dict = self._create_features(df, symbol)

            if len(X) < 50:
                logger.warning(f"  {symbol}: мало примеров для обучения ({len(X)})")
                return False

            # Обучаем модели для разных горизонтов
            models = {}
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            horizons = {
                '1h': 4,    # 4 свечи по 15м
                '4h': 16,   # 16 свечей
                '12h': 48,  # 48 свечей
                '24h': 96,  # 96 свечей
            }

            best_score = 0
            
            for horizon_name, candles in horizons.items():
                if horizon_name in y_dict:
                    y = y_dict[horizon_name]
                    
                    # Убираем NaN
                    mask = ~np.isnan(y)
                    X_clean = X_scaled[mask]
                    y_clean = y[mask]
                    
                    if len(y_clean) < 30:
                        continue

                    # Делим на train/test
                    split = int(len(X_clean) * 0.8)
                    X_train, X_test = X_clean[:split], X_clean[split:]
                    y_train, y_test = y_clean[:split], y_clean[split:]

                    if len(X_test) < 5:
                        X_train, X_test = X_clean[:-5], X_clean[-5:]
                        y_train, y_test = y_clean[:-5], y_clean[-5:]

                    # Ансамбль моделей
                    model = GradientBoostingRegressor(
                        n_estimators=200,
                        max_depth=6,
                        learning_rate=0.05,
                        random_state=42
                    )
                    
                    try:
                        model.fit(X_train, y_train)
                        score = model.score(X_test, y_test)
                        
                        models[horizon_name] = {
                            'model': model,
                            'score': max(0, score),  # R² score
                            'mae': np.mean(np.abs(y_test - model.predict(X_test))),  # Средняя ошибка
                        }
                        
                        if score > best_score:
                            best_score = score
                            
                    except Exception as e:
                        logger.error(f"    Ошибка обучения {horizon_name}: {e}")

            if len(models) >= 2:
                self.models[symbol] = {
                    'models': models,
                    'scaler': scaler,
                    'feature_names': self._get_feature_names(),
                    'trained_at': datetime.now().isoformat(),
                    'best_score': best_score,
                    'samples': len(X),
                }
                self.last_train_time[symbol] = datetime.now()
                
                # Делаем первый прогноз
                await self.predict(symbol)
                
                logger.info(f"  ✅ {symbol}: {len(models)} горизонта, "
                           f"лучший R²={best_score:.3f}, "
                           f"примеров={len(X)}")
                return True

            return False

        except Exception as e:
            logger.error(f"  ❌ {symbol}: {e}")
            return False

    def _create_features(self, df: pd.DataFrame, symbol: str) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """
        Создание признаков и целевых переменных.
        
        Признаки (40+):
        - Технические индикаторы
        - Лаговые цены (1, 2, 3, 5, 10, 20 свечей назад)
        - Временные метки
        - Паттерны свечей
        """
        features = []
        
        for i in range(100, len(df) - 96):  # Оставляем место для прогноза
            row = df.iloc[i]
            
            # Текущие индикаторы
            feat = [
                row.get('RSI', 50),
                row.get('MACD', 0),
                row.get('MACD_signal', 0),
                row.get('MACD_hist', 0),
                row.get('ADX', 20),
                row.get('ATR_pct', 1),
                row.get('BB_width', 0.02),
                row.get('momentum', 0),
                row.get('volume_ratio', 1),
                
                # EMA расстояния
                (row['close'] - row.get('EMA9', row['close'])) / row.get('EMA9', row['close']) * 100,
                (row['close'] - row.get('EMA21', row['close'])) / row.get('EMA21', row['close']) * 100,
                (row['close'] - row.get('EMA50', row['close'])) / row.get('EMA50', row['close']) * 100,
                
                # Свечные паттерны
                row.get('body_pct', 0),
                row.get('upper_wick', 0) / (abs(row.get('body', 0.01)) + 0.0001),
                row.get('lower_wick', 0) / (abs(row.get('body', 0.01)) + 0.0001),
                
                # Время
                np.sin(row.name.hour / 24 * 2 * np.pi) if hasattr(row.name, 'hour') else 0,
                np.cos(row.name.hour / 24 * 2 * np.pi) if hasattr(row.name, 'hour') else 0,
                float(row.name.weekday()) if hasattr(row.name, 'weekday') else 0,
            ]
            
            # Лаговые цены (изменения за периоды)
            current_price = row['close']
            for lag in [1, 2, 3, 5, 10, 20]:
                if i - lag >= 0:
                    lag_price = df['close'].iloc[i - lag]
                    feat.append((current_price - lag_price) / lag_price * 100)
                else:
                    feat.append(0)
            
            features.append(feat)

        X = np.array(features, dtype=float)
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        # Целевые переменные (прогнозы на разные горизонты)
        y_dict = {}
        current_prices = df['close'].iloc[100:len(df)-96].values
        
        horizons = {'1h': 4, '4h': 16, '12h': 48, '24h': 96}
        
        for name, candles in horizons.items():
            future_prices = df['close'].iloc[100+candles:len(df)-96+candles].values
            
            # Выравниваем длину
            min_len = min(len(current_prices), len(future_prices))
            if min_len > 0:
                changes = (future_prices[:min_len] - current_prices[:min_len]) / current_prices[:min_len] * 100
                y_dict[name] = changes

        # Обрезаем X до минимальной длины y
        min_features = min([len(y) for y in y_dict.values()]) if y_dict else len(X)
        X = X[:min_features]

        return X, y_dict

    def _get_feature_names(self) -> list:
        return [
            'RSI', 'MACD', 'MACD_signal', 'MACD_hist', 'ADX', 'ATR_pct',
            'BB_width', 'momentum', 'volume_ratio',
            'EMA9_dist', 'EMA21_dist', 'EMA50_dist',
            'body_pct', 'upper_wick', 'lower_wick',
            'hour_sin', 'hour_cos', 'weekday',
            'lag_1', 'lag_2', 'lag_3', 'lag_5', 'lag_10', 'lag_20'
        ]

    async def predict(self, symbol: str) -> Optional[Dict]:
        """
        Прогноз цены для пары на все горизонты.
        Возвращает словарь с прогнозами и уверенностью.
        """
        if symbol not in self.models:
            return None

        try:
            # Загружаем свежие данные
            df = await self.fetcher(symbol, "15m", 150)
            if df.empty:
                return None

            from indicators import Indicators
            df = Indicators.add_all(df)

            # Создаём признаки для текущего момента
            features = self._create_current_features(df)
            if features is None:
                return None

            # Масштабируем
            model_data = self.models[symbol]
            scaler = model_data['scaler']
            features_scaled = scaler.transform(features)

            # Прогнозы по всем горизонтам
            predictions = {}
            current_price = df['close'].iloc[-1]

            for horizon, model_info in model_data['models'].items():
                model = model_info['model']
                predicted_change = model.predict(features_scaled)[0]
                predicted_price = current_price * (1 + predicted_change / 100)

                # Уверенность на основе R² и размера прогноза
                r2_score = model_info['score']
                mae = model_info['mae']
                
                # Уверенность: комбинация R² и относительной ошибки
                confidence = min(95, max(25, r2_score * 100))
                
                # Если прогноз слишком маленький — уверенность ниже
                if abs(predicted_change) < 0.5:
                    confidence *= 0.8

                predictions[horizon] = {
                    'current_price': round(current_price, 4),
                    'predicted_price': round(predicted_price, 4),
                    'change_pct': round(predicted_change, 2),
                    'confidence': round(confidence, 1),
                    'direction': 'UP' if predicted_change > 0 else 'DOWN',
                    'r2_score': round(r2_score, 3),
                    'mae_pct': round(mae, 3),
                }

            # Сохраняем прогноз
            self.predictions[symbol] = {
                'predictions': predictions,
                'timestamp': datetime.now().isoformat(),
                'current_price': current_price,
            }

            return self.predictions[symbol]

        except Exception as e:
            logger.error(f"Ошибка прогноза {symbol}: {e}")
            return None

    def _create_current_features(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        """Создание признаков для текущего момента."""
        if len(df) < 100:
            return None

        row = df.iloc[-1]
        current_price = row['close']

        feat = [
            row.get('RSI', 50),
            row.get('MACD', 0),
            row.get('MACD_signal', 0),
            row.get('MACD_hist', 0),
            row.get('ADX', 20),
            row.get('ATR_pct', 1),
            row.get('BB_width', 0.02),
            row.get('momentum', 0),
            row.get('volume_ratio', 1),
            (current_price - row.get('EMA9', current_price)) / row.get('EMA9', current_price) * 100,
            (current_price - row.get('EMA21', current_price)) / row.get('EMA21', current_price) * 100,
            (current_price - row.get('EMA50', current_price)) / row.get('EMA50', current_price) * 100,
            row.get('body_pct', 0),
            row.get('upper_wick', 0) / (abs(row.get('body', 0.01)) + 0.0001),
            row.get('lower_wick', 0) / (abs(row.get('body', 0.01)) + 0.0001),
            np.sin(datetime.now().hour / 24 * 2 * np.pi),
            np.cos(datetime.now().hour / 24 * 2 * np.pi),
            float(datetime.now().weekday()),
        ]

        # Лаговые признаки
        for lag in [1, 2, 3, 5, 10, 20]:
            if len(df) > lag:
                lag_price = df['close'].iloc[-1 - lag]
                feat.append((current_price - lag_price) / lag_price * 100)
            else:
                feat.append(0)

        return np.array([feat], dtype=float)

    def should_reopen_position(self, symbol: str, position_type: str) -> Tuple[bool, str]:
        """
        Проверка: стоит ли переоткрыть позицию на основе прогноза.
        Используется при управлении позициями.
        """
        if symbol not in self.predictions:
            return False, "Нет прогноза"

        pred = self.predictions[symbol]
        if not pred or 'predictions' not in pred:
            return False, "Нет данных прогноза"

        # Смотрим прогноз на 4 часа
        forecast_4h = pred['predictions'].get('4h')
        if not forecast_4h:
            return False, "Нет прогноза на 4ч"

        direction = forecast_4h['direction']
        confidence = forecast_4h['confidence']
        change = forecast_4h['change_pct']

        # Проверяем совпадение с позицией
        if position_type == 'BUY' and direction == 'UP' and confidence > 50:
            return True, f"Прогноз ↑ на {change:+.1f}% (уверенность {confidence:.0f}%)"
        elif position_type == 'SELL' and direction == 'DOWN' and confidence > 50:
            return True, f"Прогноз ↓ на {change:+.1f}% (уверенность {confidence:.0f}%)"
        elif confidence < 40:
            return False, f"Слабый прогноз (уверенность {confidence:.0f}%)"
        else:
            return False, f"Прогноз противоречит позиции"

    def get_prediction_summary(self, symbol: str) -> str:
        """Краткий прогноз для Telegram."""
        if symbol not in self.predictions:
            return f"{symbol}: нет прогноза"

        pred = self.predictions[symbol]
        current = pred.get('current_price', 0)
        
        lines = [f"📈 {symbol} @ {current:.4f}$"]
        
        for horizon in ['1h', '4h', '12h', '24h']:
            if horizon in pred['predictions']:
                p = pred['predictions'][horizon]
                emoji = "🟢" if p['direction'] == 'UP' else "🔴"
                lines.append(
                    f"  {emoji} {horizon}: {p['predicted_price']:.4f}$ "
                    f"({p['change_pct']:+.1f}%) "
                    f"[уверенность: {p['confidence']:.0f}%]"
                )
        
        return "\n".join(lines)

    async def auto_retrain_if_needed(self, symbol: str):
        """Автоматическое переобучение раз в 4 часа."""
        if symbol in self.last_train_time:
            elapsed = (datetime.now() - self.last_train_time[symbol]).total_seconds()
            if elapsed < 14400:  # 4 часа
                return
        
        logger.info(f"🔄 Переобучение {symbol}...")
        await self.train_single_pair(symbol, 500)
        self._save()

    def _save(self):
        """Сохранение моделей."""
        try:
            save_data = {
                'models': self.models,
                'last_train_time': {k: v.isoformat() for k, v in self.last_train_time.items()},
                'predictions': self.predictions,
            }
            with open(config.MODELS_DIR / "price_predictor.pkl", 'wb') as f:
                pickle.dump(save_data, f)
            logger.info(f"💾 PricePredictor сохранён ({len(self.models)} пар)")
        except Exception as e:
            logger.error(f"Ошибка сохранения PricePredictor: {e}")

    def _load(self):
        """Загрузка моделей."""
        try:
            path = config.MODELS_DIR / "price_predictor.pkl"
            if path.exists():
                with open(path, 'rb') as f:
                    data = pickle.load(f)
                self.models = data.get('models', {})
                self.predictions = data.get('predictions', {})
                
                # Восстанавливаем время обучения
                for k, v in data.get('last_train_time', {}).items():
                    try:
                        self.last_train_time[k] = datetime.fromisoformat(v)
                    except Exception:
                        pass
                
                if self.models:
                    self.is_trained = True
                    logger.info(f"✅ PricePredictor загружен ({len(self.models)} пар)")
                    return True
        except Exception as e:
            logger.warning(f"PricePredictor не загружен: {e}")
        return False