"""
Файл: market_regime.py
HMM для определения рыночного режима.
"""

from typing import Dict

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from logger import logger


class MarketRegimeHMM:
    """Скрытые Марковские Модели для рыночных режимов."""

    def __init__(self, n_states: int = 4):
        self.n_states = n_states
        self.model = None
        self.scaler = None  # Создаём при обучении
        self._fitted = False

        self.state_names = {
            0: "Тренд вверх",
            1: "Боковик",
            2: "Тренд вниз",
            3: "Волатильность",
        }
        self.optimal_strategies = {
            0: ["trend", "scalping"],
            1: ["counter_trend", "grid"],
            2: ["trend"],
            3: ["scalping"],
        }
        self.risk_multipliers = {0: 0.8, 1: 1.0, 2: 0.8, 3: 0.5}

    # ------------------------------------------------------------------
    def _extract_features(self, df: pd.DataFrame) -> np.ndarray:
        """Извлечение фиксированного набора признаков (8 штук)."""
        features = []

        # 1-4: Доходность за периоды
        for period in [1, 5, 10, 20]:
            features.append(df["close"].pct_change(period).fillna(0).values)

        # 5-6: Волатильность
        for period in [10, 20]:
            features.append(
                df["close"].pct_change().rolling(period).std().fillna(0).values
            )

        # 7: Отношение объёма
        features.append(
            (df["volume"] / df["volume"].rolling(20).mean()).fillna(1).values
        )

        # 8: RSI / 100 (если есть)
        if "RSI" in df.columns:
            features.append((df["RSI"] / 100).fillna(0.5).values)
        else:
            # Заглушка, если RSI ещё не посчитан
            features.append(np.full(len(df), 0.5))

        X = np.column_stack(features)
        return np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    # ------------------------------------------------------------------
    def fit(self, df: pd.DataFrame):
        """Обучение HMM."""
        try:
            from hmmlearn import hmm

            X = self._extract_features(df)
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)

            self.model = hmm.GaussianHMM(
                n_components=self.n_states,
                covariance_type="diag",
                n_iter=100,
                random_state=42,
            )
            self.model.fit(X_scaled)
            self._fitted = True
            logger.info(f"HMM обучена: {self.n_states} состояний, признаков: {X.shape[1]}")
        except ImportError:
            logger.warning("hmmlearn не установлен – HMM отключена")
        except Exception as e:
            logger.error(f"Ошибка обучения HMM: {e}")
            self._fitted = False

        return self

    # ------------------------------------------------------------------
    def predict(self, df: pd.DataFrame) -> Dict:
        """Предсказание текущего режима."""
        if not self._fitted or self.model is None or self.scaler is None:
            return self._default()

        try:
            X = self._extract_features(df)
            X_scaled = self.scaler.transform(X)

            states = self.model.predict(X_scaled)
            current = states[-1]
            probs = self.model.predict_proba(X_scaled)[-1]

            recent = states[-50:] if len(states) >= 50 else states
            mode_state = np.bincount(recent).argmax()
            stability = np.sum(recent == mode_state) / len(recent)

            return {
                "state": int(current),
                "state_name": self.state_names.get(current, f"State {current}"),
                "probability": float(probs[current]),
                "stability": float(stability),
                "optimal_strategies": self.optimal_strategies.get(current, []),
                "risk_multiplier": self.risk_multipliers.get(current, 1.0),
            }
        except Exception as e:
            logger.error(f"Ошибка HMM predict: {e}")
            return self._default()

    # ------------------------------------------------------------------
    @staticmethod
    def _default() -> Dict:
        return {
            "state": 1,
            "state_name": "Неопределённый",
            "probability": 0.5,
            "stability": 0.5,
            "optimal_strategies": ["trend", "counter_trend"],
            "risk_multiplier": 1.0,
        }