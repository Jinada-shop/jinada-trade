"""
Файл: ensemble_ai.py
Ансамбль AI моделей (LightGBM + XGBoost + RandomForest).
"""

import pickle
from datetime import datetime
from typing import Dict, Tuple

import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

from config import config
from database import get_db
from logger import logger


class EnsembleAI:
    """Ансамбль из 3 моделей. Сигнал проходит при 2/3 голосов."""

    def __init__(self):
        self.models = {}
        self.scaler = StandardScaler()
        self.is_trained = False
        self.last_train = None
        self.weights = {}  # Вес каждой модели на основе accuracy

    def _get_data(self) -> Tuple[np.ndarray, np.ndarray]:
        with get_db() as db:
            rows = db.execute("""
                SELECT t.direction, t.pnl, s.rsi, s.volume_ratio,
                       s.ml_confidence, s.hmm_state
                FROM trades t
                LEFT JOIN signals s ON t.signal_id = s.id
                WHERE t.status = 'CLOSED' AND t.pnl IS NOT NULL
                ORDER BY t.entry_time DESC LIMIT 2000
            """).fetchall()

        if len(rows) < 50:
            return np.array([]), np.array([])

        X, y = [], []
        for row in rows:
            X.append([
                float(row['rsi'] or 50),
                float(row['volume_ratio'] or 1),
                float(row['ml_confidence'] or 0.5),
                float(row['hmm_state'] or 1),
                1 if row['direction'] == 'LONG' else 0,
            ])
            y.append(1 if (row['pnl'] or 0) > 0 else 0)

        return np.array(X), np.array(y)

    def train(self, force: bool = False):
        if self.is_trained and not force and self.last_train:
            if (datetime.now() - self.last_train).total_seconds() / 3600 < 12:
                return

        X, y = self._get_data()
        if len(X) < 50:
            return

        try:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        except ValueError:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        X_train_s = self.scaler.fit_transform(X_train)
        X_test_s = self.scaler.transform(X_test)

        # Три модели
        models = {
            'rf': RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42),
            'gb': GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42),
            'lr': LogisticRegression(max_iter=1000),
        }

        for name, model in models.items():
            try:
                model.fit(X_train_s, y_train)
                acc = model.score(X_test_s, y_test)
                self.models[name] = model
                self.weights[name] = max(acc, 0.5)
                logger.info(f"   Ensemble {name}: accuracy={acc:.1%}")
            except Exception:
                pass

        if len(self.models) >= 2:
            self.is_trained = True
            self.last_train = datetime.now()
            self._save()
            logger.info(f"✅ Ensemble AI обучен! Моделей: {len(self.models)}")

    def _save(self):
        try:
            config.MODELS_DIR.mkdir(exist_ok=True)
            with open(config.MODELS_DIR / "ensemble.pkl", 'wb') as f:
                pickle.dump({
                    'models': self.models, 'scaler': self.scaler, 'weights': self.weights,
                }, f)
        except Exception as e:
            logger.error(f"Ошибка сохранения Ensemble: {e}")

    def _load(self):
        try:
            path = config.MODELS_DIR / "ensemble.pkl"
            if path.exists():
                with open(path, 'rb') as f:
                    data = pickle.load(f)
                self.models = data['models']
                self.scaler = data['scaler']
                self.weights = data.get('weights', {})
                self.is_trained = True
                logger.info("✅ Ensemble AI загружен")
        except Exception:
            pass

    def predict(self, signal: Dict) -> Dict:
        """Голосование ансамбля."""
        if not self.is_trained or len(self.models) < 2:
            return {'ai_score': 0.5, 'ai_signal': 'NEUTRAL', 'ai_pass': True, 'votes': 0}

        X = np.array([[
            float(signal.get('rsi', 50)),
            float(signal.get('volume_ratio', 1)),
            float(signal.get('confidence', 0.5)),
            float(signal.get('hmm_state', 1)),
            1 if signal.get('type') == 'BUY' else 0,
        ]])

        try:
            X_s = self.scaler.transform(X)
        except Exception:
            X_s = X

        votes_for = 0
        total_votes = 0
        weighted_score = 0
        total_weight = 0

        for name, model in self.models.items():
            try:
                proba = model.predict_proba(X_s)[0]
                score = float(proba[1])
                weight = self.weights.get(name, 0.5)
                weighted_score += score * weight
                total_weight += weight
                total_votes += 1
                if score > 0.5:
                    votes_for += 1
            except Exception:
                pass

        if total_votes == 0:
            return {'ai_score': 0.5, 'ai_signal': 'NEUTRAL', 'ai_pass': True, 'votes': 0}

        final_score = weighted_score / total_weight if total_weight > 0 else 0.5
        ai_pass = votes_for >= total_votes * 0.5  # Минимум 50% голосов

        if final_score >= 0.65:
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
            'models': total_votes,
        }