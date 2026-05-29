"""
Файл: ai_engine.py
AI/ML движок для фильтрации и улучшения сигналов.
"""

import os
import pickle
from datetime import datetime
from typing import Dict, Tuple

import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score

from config import config
from database import get_db
from logger import logger


class AIEngine:
    """AI слой для прогнозирования успешности сигналов."""

    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.last_train_time = None
        self.model_path = config.MODELS_DIR / "ai_model.pkl"
        self.scaler_path = config.MODELS_DIR / "ai_scaler.pkl"
        self._load_model()

    def _load_model(self):
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
                with open(self.scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                self.is_trained = True
                logger.info("✅ AI модель загружена")
        except Exception as e:
            logger.warning(f"AI модель не загружена: {e}")

    def _save_model(self):
        try:
            config.MODELS_DIR.mkdir(exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            with open(self.scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)
        except Exception as e:
            logger.error(f"Ошибка сохранения AI: {e}")

    def _get_training_data(self) -> Tuple[np.ndarray, np.ndarray]:
        with get_db() as db:
            rows = db.execute("""
                SELECT t.direction, t.pnl, s.rsi, s.volume_ratio,
                       s.ml_confidence, s.hmm_state
                FROM trades t
                LEFT JOIN signals s ON t.signal_id = s.id
                WHERE t.status = 'CLOSED' AND t.pnl IS NOT NULL
                ORDER BY t.entry_time DESC LIMIT 1000
            """).fetchall()

        if len(rows) < 50:
            return np.array([]), np.array([])

        features, labels = [], []
        for row in rows:
            features.append([
                float(row['rsi'] or 50),
                float(row['volume_ratio'] or 1),
                float(row['ml_confidence'] or 0.5),
                float(row['hmm_state'] or 1),
                1 if row['direction'] == 'LONG' else 0,
            ])
            labels.append(1 if (row['pnl'] or 0) > 0 else 0)

        return np.array(features), np.array(labels)

    def train(self, force: bool = False):
        if self.is_trained and not force and self.last_train_time:
            hours = (datetime.now() - self.last_train_time).total_seconds() / 3600
            if hours < 24:
                return

        X, y = self._get_training_data()
        if len(X) < 50:
            logger.warning(f"⚠️ Мало данных для AI: {len(X)} сделок")
            return

        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
        except ValueError:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        models = {
            'rf': RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42),
            'gb': GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42),
            'lr': LogisticRegression(max_iter=1000),
        }

        best_model, best_score = None, 0
        for name, model in models.items():
            try:
                model.fit(X_train_scaled, y_train)
                y_pred = model.predict(X_test_scaled)
                acc = accuracy_score(y_test, y_pred)
                if acc > best_score:
                    best_score = acc
                    best_model = model
            except Exception:
                pass

        if best_model:
            self.model = best_model
            self.is_trained = True
            self.last_train_time = datetime.now()
            self._save_model()
            logger.info(f"✅ AI обучен! Сделок: {len(X)}, Точность: {best_score:.0%}")

    def predict(self, signal: Dict) -> Dict:
        if not self.is_trained:
            return {'ai_score': 0.5, 'ai_signal': 'NEUTRAL', 'ai_pass': True, 'ai_confidence': 0.0}

        features = np.array([[
            float(signal.get('rsi', 50)),
            float(signal.get('volume_ratio', 1)),
            float(signal.get('confidence', 0.5)),
            float(signal.get('hmm_state', 1)),
            1 if signal.get('type') == 'BUY' else 0,
        ]])

        try:
            features_scaled = self.scaler.transform(features)
            proba = self.model.predict_proba(features_scaled)[0]
            ai_score = float(proba[1])
        except Exception:
            ai_score = 0.5

        if ai_score >= 0.65:
            ai_signal, ai_pass = 'STRONG', True
        elif ai_score >= 0.45:
            ai_signal, ai_pass = 'NEUTRAL', True
        else:
            ai_signal, ai_pass = 'WEAK', False

        return {
            'ai_score': round(ai_score, 3),
            'ai_signal': ai_signal,
            'ai_pass': ai_pass,
            'ai_confidence': round(abs(ai_score - 0.5) * 2, 3),
        }

    def get_stats(self) -> Dict:
        if not self.is_trained:
            return {'status': 'Не обучена', 'trained': False}
        X, y = self._get_training_data()
        return {
            'status': 'Обучена',
            'trained': True,
            'total_trades': len(y),
            'win_rate': f"{np.mean(y)*100:.0f}%" if len(y) > 0 else "N/A",
            'model_type': type(self.model).__name__,
            'last_train': self.last_train_time.strftime('%d.%m.%Y %H:%M') if self.last_train_time else 'N/A',
        }

    def needs_training(self) -> bool:
        if not self.is_trained:
            return True
        if self.last_train_time:
            return (datetime.now() - self.last_train_time).total_seconds() / 3600 >= 24
        return False