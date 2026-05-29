"""
Файл: lstm_predictor.py
LSTM нейросеть для прогноза направления цены.
"""

import os
import pickle
from datetime import datetime
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from config import config
from logger import logger


class LSTMPredictor:
    """
    Прогноз направления цены на 1-4 часа.
    Использует простую нейросеть (без тяжёлых зависимостей).
    """

    def __init__(self):
        self.scaler = MinMaxScaler()
        self.weights = None
        self.bias = None
        self.is_trained = False
        self.accuracy = 0.0
        self.model_path = config.MODELS_DIR / "lstm_weights.pkl"

        if os.path.exists(self.model_path):
            self._load()

    def _load(self):
        try:
            with open(self.model_path, 'rb') as f:
                data = pickle.load(f)
            self.weights = data['weights']
            self.bias = data['bias']
            self.scaler = data['scaler']
            self.is_trained = True
            self.accuracy = data.get('accuracy', 0)
            logger.info(f"✅ LSTM модель загружена (точность: {self.accuracy:.0%})")
        except Exception as e:
            logger.warning(f"LSTM модель не загружена: {e}")

    def _save(self):
        try:
            config.MODELS_DIR.mkdir(exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump({
                    'weights': self.weights,
                    'bias': self.bias,
                    'scaler': self.scaler,
                    'accuracy': self.accuracy,
                }, f)
        except Exception as e:
            logger.error(f"Ошибка сохранения LSTM: {e}")

    def _prepare_data(self, df: pd.DataFrame, lookback: int = 20) -> Tuple[np.ndarray, np.ndarray]:
        """Подготовка данных для обучения."""
        close = df['close'].values.reshape(-1, 1)
        scaled = self.scaler.fit_transform(close)

        X, y = [], []
        for i in range(lookback, len(scaled) - 4):  # Прогноз на 4 часа
            X.append(scaled[i-lookback:i].flatten())
            # 1 = цена выросла через 4 часа, 0 = упала
            y.append(1 if scaled[i+4][0] > scaled[i][0] else 0)

        return np.array(X), np.array(y)

    def train(self, df: pd.DataFrame) -> Dict:
        """Обучение простой нейросети."""
        if len(df) < 100:
            return {'status': 'недостаточно данных'}

        try:
            X, y = self._prepare_data(df)

            if len(X) < 50:
                return {'status': f'мало данных: {len(X)}'}

            # Простая нейросеть (один скрытый слой)
            input_size = X.shape[1]
            hidden_size = 16

            # Инициализация весов
            np.random.seed(42)
            self.weights = {
                'w1': np.random.randn(input_size, hidden_size) * 0.01,
                'w2': np.random.randn(hidden_size, 1) * 0.01,
            }
            self.bias = {
                'b1': np.zeros(hidden_size),
                'b2': np.zeros(1),
            }

            # Обучение (простой градиентный спуск)
            learning_rate = 0.01
            for epoch in range(200):
                # Forward pass
                z1 = X @ self.weights['w1'] + self.bias['b1']
                a1 = np.maximum(0, z1)  # ReLU
                z2 = a1 @ self.weights['w2'] + self.bias['b2']
                pred = 1 / (1 + np.exp(-z2))  # Sigmoid

                # Backward pass (упрощённый)
                dz2 = (pred - y.reshape(-1, 1)) / len(y)
                dw2 = a1.T @ dz2
                db2 = np.sum(dz2, axis=0)

                da1 = dz2 @ self.weights['w2'].T
                dz1 = da1 * (z1 > 0)
                dw1 = X.T @ dz1
                db1 = np.sum(dz1, axis=0)

                # Обновление
                self.weights['w1'] -= learning_rate * dw1
                self.weights['w2'] -= learning_rate * dw2
                self.bias['b1'] -= learning_rate * db1
                self.bias['b2'] -= learning_rate * db2

            # Оценка точности
            predictions = (pred.flatten() > 0.5).astype(int)
            self.accuracy = np.mean(predictions == y)
            self.is_trained = True
            self._save()

            logger.info(f"✅ LSTM обучена! Точность: {self.accuracy:.0%}, данных: {len(X)}")
            return {
                'status': 'обучена',
                'accuracy': f'{self.accuracy:.0%}',
                'samples': len(X),
            }

        except Exception as e:
            logger.error(f"Ошибка обучения LSTM: {e}")
            return {'status': f'ошибка: {e}'}

    def predict(self, df: pd.DataFrame) -> Dict:
        """Прогноз направления на 4 часа."""
        if not self.is_trained:
            return {'prediction': 'unknown', 'confidence': 0, 'direction': 'hold'}

        try:
            lookback = 20
            close = df['close'].values.reshape(-1, 1)

            if len(close) < lookback:
                return {'prediction': 'unknown', 'confidence': 0}

            scaled = self.scaler.transform(close)
            X = scaled[-lookback:].flatten().reshape(1, -1)

            # Forward pass
            z1 = X @ self.weights['w1'] + self.bias['b1']
            a1 = np.maximum(0, z1)
            z2 = a1 @ self.weights['w2'] + self.bias['b2']
            prob = 1 / (1 + np.exp(-z2))

            up_prob = float(prob[0][0])
            confidence = abs(up_prob - 0.5) * 2

            if up_prob > 0.6:
                direction = 'up'
            elif up_prob < 0.4:
                direction = 'down'
            else:
                direction = 'neutral'

            return {
                'prediction': f'Рост {up_prob:.0%}' if up_prob > 0.5 else f'Падение {1-up_prob:.0%}',
                'direction': direction,
                'confidence': round(confidence, 2),
                'up_probability': round(up_prob, 3),
            }

        except Exception as e:
            return {'prediction': 'error', 'confidence': 0}