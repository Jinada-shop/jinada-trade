"""
Файл: deep_ai_engine.py — AI С УЧЁТОМ РЕЖИМА РЫНКА
"""

import pickle
from datetime import datetime
from typing import Dict, Tuple, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

from config import config
from logger import logger


class DeepAIEngine:
    """Для каждой пары — своя AI модель. Учится на истории графика."""

    def __init__(self, fetcher=None):
        self.fetcher = fetcher
        self.models: Dict[str, Dict] = {}
        self.is_trained = False
        self.training_samples = 0
        self._load()

    async def train_on_history(self, symbols: list = None, hours: int = 500):
        """Обучение отдельных моделей для каждой пары на истории графика."""
        if symbols is None:
            symbols = ["BTCUSDT", "ETHUSDT"]

        logger.info("=" * 60)
        logger.info(f"ОБУЧЕНИЕ AI ДЛЯ {len(symbols)} ПАР (по {hours} часов истории)")
        logger.info("=" * 60)

        total_samples = 0
        trained_pairs = 0

        for symbol in symbols:
            try:
                result = await self._train_single_pair(symbol, hours)
                if result:
                    trained_pairs += 1
                    total_samples += result['samples']
                    logger.info(f"  {symbol}: {result['models']} модели, "
                               f"точность {result['accuracy']:.0%}, "
                               f"{result['samples']} примеров")
            except Exception as e:
                logger.error(f"  {symbol}: ошибка — {e}")

        if trained_pairs > 0:
            self.is_trained = True
            self.training_samples = total_samples
            self._save()
            logger.info(f"✅ Обучено пар: {trained_pairs}, всего примеров: {total_samples}")
        else:
            logger.warning("⚠️ Не удалось обучить ни одной модели!")

    async def _train_single_pair(self, symbol: str, hours: int = 500) -> Optional[Dict]:
        """Обучение модели для одной пары на истории графика."""
        limit = hours * 4
        df = await self.fetcher(symbol, "15m", limit)

        if df.empty or len(df) < 50:
            logger.warning(f"  {symbol}: недостаточно данных ({len(df)} свечей)")
            return None

        features, labels = self._create_training_data(df, symbol)

        if len(features) < 30:
            logger.warning(f"  {symbol}: мало примеров ({len(features)})")
            return None

        X, y = self._balance_classes(features, labels)

        if len(X) < 30:
            return None

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42, stratify=y
            )
        except ValueError:
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42
            )

        models_to_train = {
            'rf': RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42),
            'gb': GradientBoostingClassifier(n_estimators=200, max_depth=5, random_state=42),
            'lr': LogisticRegression(max_iter=2000, random_state=42),
            'rf2': RandomForestClassifier(n_estimators=100, max_depth=8, random_state=24),
            'gb2': GradientBoostingClassifier(n_estimators=150, max_depth=4, random_state=24),
        }

        best_models = {}
        best_accuracy = 0

        for name, model in models_to_train.items():
            try:
                model.fit(X_train, y_train)
                score = model.score(X_test, y_test)

                if score > 0.50:
                    best_models[name] = model
                    if score > best_accuracy:
                        best_accuracy = score
            except Exception:
                pass

        if len(best_models) >= 2:
            self.models[symbol] = {
                'models': best_models,
                'scaler': scaler,
                'accuracy': best_accuracy,
                'samples': len(X),
                'trained_at': datetime.now().isoformat(),
            }
            return {
                'models': len(best_models),
                'accuracy': best_accuracy,
                'samples': len(X),
            }

        return None

    def _create_training_data(self, df: pd.DataFrame, symbol: str) -> Tuple[np.ndarray, np.ndarray]:
        """Создание обучающих данных из истории графика."""
        from indicators import Indicators
        df = Indicators.add_all(df)

        features = []
        labels = []

        look_forward = 12

        for i in range(50, len(df) - look_forward):
            row = df.iloc[i]
            future_row = df.iloc[i + look_forward]

            rsi = row.get('RSI', 50)
            volume_ratio = row.get('volume_ratio', 1)
            macd = row.get('MACD', 0)
            macd_signal = row.get('MACD_signal', 0)
            adx = row.get('ADX', 20)
            atr_pct = row.get('ATR_pct', 1)
            bb_width = row.get('BB_width', 0.02)
            momentum = row.get('momentum', 0)

            ema9 = row.get('EMA9', row['close'])
            ema21 = row.get('EMA21', row['close'])
            ema50 = row.get('EMA50', row['close'])
            ema_distance_9 = (row['close'] - ema9) / ema9 * 100
            ema_distance_21 = (row['close'] - ema21) / ema21 * 100
            ema_distance_50 = (row['close'] - ema50) / ema50 * 100

            hour = row.name.hour if hasattr(row.name, 'hour') else 0
            day = row.name.weekday() if hasattr(row.name, 'weekday') else 0

            body = abs(row['close'] - row['open'])
            upper_wick = row['high'] - max(row['close'], row['open'])
            lower_wick = min(row['close'], row['open']) - row['low']
            body_pct = body / row['open'] * 100 if row['open'] > 0 else 0
            wick_ratio = (upper_wick + lower_wick) / (body + 0.0001)

            feature_vector = [
                float(rsi),
                float(volume_ratio),
                float(macd),
                float(macd_signal),
                float(adx),
                float(atr_pct),
                float(bb_width),
                float(momentum),
                float(ema_distance_9),
                float(ema_distance_21),
                float(ema_distance_50),
                np.sin(hour / 24 * 2 * np.pi),
                np.cos(hour / 24 * 2 * np.pi),
                float(day),
                float(body_pct),
                float(wick_ratio),
            ]

            future_change = (future_row['close'] - row['close']) / row['close'] * 100

            if rsi < 55 and volume_ratio > 1.05 and future_change > 0.2:
                labels.append(1)
                features.append(feature_vector)
            elif rsi > 45 and volume_ratio > 1.05 and future_change < -0.2:
                labels.append(1)
                features.append(feature_vector)
            elif rsi < 35 and volume_ratio > 0.9 and future_change < -0.15:
                labels.append(0)
                features.append(feature_vector)
            elif rsi > 65 and volume_ratio > 0.9 and future_change > 0.15:
                labels.append(0)
                features.append(feature_vector)

        return np.array(features), np.array(labels)

    def _balance_classes(self, X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Балансировка классов."""
        pos_idx = np.where(y == 1)[0]
        neg_idx = np.where(y == 0)[0]

        if len(pos_idx) == 0 or len(neg_idx) == 0:
            return X, y

        if len(pos_idx) > len(neg_idx):
            pos_idx = np.random.choice(pos_idx, size=len(neg_idx), replace=False)
        else:
            neg_idx = np.random.choice(neg_idx, size=len(pos_idx), replace=False)

        balanced_idx = np.concatenate([pos_idx, neg_idx])
        return X[balanced_idx], y[balanced_idx]

    def predict(self, signal: Dict, regime: Optional[Dict] = None) -> Dict:
        """Предсказание с учётом режима рынка."""
        symbol = signal.get('symbol', '')

        if symbol not in self.models:
            if self.models:
                symbol = list(self.models.keys())[0]
            else:
                return {'ai_score': 0.5, 'ai_signal': 'NEUTRAL', 'ai_pass': True, 'votes': '0/0', 'pair_accuracy': 0}

        model_data = self.models[symbol]
        models = model_data['models']
        scaler = model_data['scaler']

        if len(models) < 2:
            return {'ai_score': 0.5, 'ai_signal': 'NEUTRAL', 'ai_pass': True, 'votes': '0/0', 'pair_accuracy': 0}

        try:
            hour = datetime.now().hour
            day = datetime.now().weekday()

            features = np.array([[
                float(signal.get('rsi', 50)),
                float(signal.get('volume_ratio', 1)),
                float(signal.get('macd', 0)),
                float(signal.get('macd_signal', 0)),
                float(signal.get('adx', 20)),
                float(signal.get('atr_pct', 1)),
                float(signal.get('bb_width', 0.02)),
                float(signal.get('momentum', 0)),
                float(signal.get('ema_distance_9', 0)),
                float(signal.get('ema_distance_21', 0)),
                float(signal.get('ema_distance_50', 0)),
                np.sin(hour / 24 * 2 * np.pi),
                np.cos(hour / 24 * 2 * np.pi),
                float(day),
                float(signal.get('body_pct', 0)),
                float(signal.get('wick_ratio', 0)),
            ]])

            features_scaled = scaler.transform(features)

            votes_for = 0
            total_votes = 0

            for name, model in models.items():
                try:
                    proba = model.predict_proba(features_scaled)[0]
                    score = float(proba[1]) if len(proba) > 1 else 0.5
                    total_votes += 1
                    if score > 0.5:
                        votes_for += 1
                except Exception:
                    pass

            if total_votes == 0:
                return {'ai_score': 0.5, 'ai_signal': 'NEUTRAL', 'ai_pass': True, 'votes': '0/0', 'pair_accuracy': 0}

            final_score = votes_for / total_votes

            # Корректировка от режима рынка
            if regime:
                regime_mult = regime.get('risk_multiplier', 1.0)
                if regime_mult < 0.8:  # Волатильный рынок — снижаем уверенность
                    final_score *= 0.80
                elif regime_mult > 1.0:  # Спокойный рынок — слегка повышаем
                    final_score = min(0.95, final_score * 1.05)
                
                # Если режим "Волатильность" — снижаем
                if regime.get('state') == 3:
                    final_score *= 0.75

            final_score = min(0.95, max(0.05, final_score))
            ai_pass = votes_for >= total_votes * 0.5

            if final_score >= 0.70:
                ai_signal = 'STRONG'
            elif final_score >= 0.45:
                ai_signal = 'NEUTRAL'
            else:
                ai_signal = 'WEAK'

            return {
                'ai_score': round(final_score, 3),
                'ai_signal': ai_signal,
                'ai_pass': ai_pass,
                'votes': f"{votes_for}/{total_votes}",
                'pair_accuracy': round(model_data['accuracy'], 2),
            }

        except Exception as e:
            logger.error(f"AI predict error for {symbol}: {e}")
            return {'ai_score': 0.5, 'ai_signal': 'NEUTRAL', 'ai_pass': True, 'votes': '0/0', 'pair_accuracy': 0}

    def get_trained_pairs(self) -> list:
        return list(self.models.keys())

    def _save(self):
        try:
            with open(config.MODELS_DIR / "deep_ai_per_pair.pkl", 'wb') as f:
                pickle.dump({'models': self.models, 'trained_at': datetime.now().isoformat()}, f)
            logger.info(f"💾 AI модели сохранены ({len(self.models)} пар)")
        except Exception as e:
            logger.error(f"Ошибка сохранения AI: {e}")

    def _load(self):
        try:
            path = config.MODELS_DIR / "deep_ai_per_pair.pkl"
            if path.exists():
                with open(path, 'rb') as f:
                    data = pickle.load(f)
                self.models = data.get('models', {})
                if self.models:
                    self.is_trained = True
                    logger.info(f"✅ AI модели загружены ({len(self.models)} пар)")
                    return True
        except Exception as e:
            logger.warning(f"AI модели не загружены: {e}")
        return False