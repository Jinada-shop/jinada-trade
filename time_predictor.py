"""
Файл: time_predictor.py
ИСПРАВЛЕННЫЙ — показывает РЕАЛЬНОЕ время на основе статистики.
"""

import pickle
from datetime import datetime
from typing import Dict

import numpy as np

from config import config
from database import get_db
from logger import logger


class TimePredictor:
    """Предсказывает время до тейка/стопа на основе реальной статистики."""

    def __init__(self):
        self.avg_time_to_tp: Dict[str, float] = {}
        self.avg_time_to_sl: Dict[str, float] = {}
        self.tp_probability: Dict[str, float] = {}
        self.is_trained = False
        self.model_path = config.MODELS_DIR / "time_predictor.pkl"
        self._load()

    def _load(self):
        try:
            if self.model_path.exists():
                with open(self.model_path, 'rb') as f:
                    data = pickle.load(f)
                self.avg_time_to_tp = data.get('avg_time_to_tp', {})
                self.avg_time_to_sl = data.get('avg_time_to_sl', {})
                self.tp_probability = data.get('tp_probability', {})
                self.is_trained = True
                logger.info("✅ TimePredictor загружен")
        except Exception as e:
            logger.warning(f"TimePredictor не загружен: {e}")

    def _save(self):
        try:
            config.MODELS_DIR.mkdir(exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump({
                    'avg_time_to_tp': self.avg_time_to_tp,
                    'avg_time_to_sl': self.avg_time_to_sl,
                    'tp_probability': self.tp_probability,
                }, f)
        except Exception as e:
            logger.error(f"Ошибка сохранения TimePredictor: {e}")

    def train(self):
        """Обучение на РЕАЛЬНЫХ закрытых сделках."""
        with get_db() as db:
            rows = db.execute("""
                SELECT strategy, entry_time, exit_time, exit_reason, pnl
                FROM trades 
                WHERE status = 'CLOSED' 
                AND entry_time IS NOT NULL 
                AND exit_time IS NOT NULL
                AND exit_reason != 'shutdown'
                AND exit_reason != 'restart'
                ORDER BY exit_time DESC
                LIMIT 200
            """).fetchall()

        if len(rows) < 5:
            logger.warning(f"⚠️ TimePredictor: мало данных ({len(rows)} сделок)")
            return

        strategy_times_tp = {}
        strategy_times_sl = {}
        strategy_tp_count = {}
        strategy_total = {}

        for row in rows:
            strategy = row['strategy'] or 'unknown'
            try:
                entry = datetime.fromisoformat(row['entry_time'].replace('Z', '+00:00'))
                exit_t = datetime.fromisoformat(row['exit_time'].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                continue

            hours = (exit_t - entry).total_seconds() / 3600
            if hours <= 0 or hours > 72:  # Игнорируем аномалии
                continue

            strategy_total[strategy] = strategy_total.get(strategy, 0) + 1

            if row['exit_reason'] in ['take_profit', 'take_profit_partial'] or (row['pnl'] or 0) > 0:
                strategy_times_tp.setdefault(strategy, []).append(hours)
                strategy_tp_count[strategy] = strategy_tp_count.get(strategy, 0) + 1
            elif row['exit_reason'] in ['stop_loss'] or (row['pnl'] or 0) <= 0:
                strategy_times_sl.setdefault(strategy, []).append(hours)

        for strategy in strategy_total:
            times = strategy_times_tp.get(strategy, [])
            if times:
                self.avg_time_to_tp[strategy] = round(np.mean(times), 1)
            else:
                self.avg_time_to_tp[strategy] = 2.0  # По умолчанию 2 часа

            times = strategy_times_sl.get(strategy, [])
            if times:
                self.avg_time_to_sl[strategy] = round(np.mean(times), 1)
            else:
                self.avg_time_to_sl[strategy] = 1.0  # По умолчанию 1 час

            tp_count = strategy_tp_count.get(strategy, 0)
            total = strategy_total.get(strategy, 1)
            self.tp_probability[strategy] = round(tp_count / total * 100, 1)

        self.is_trained = True
        self._save()

        logger.info(f"✅ TimePredictor обучен! Стратегий: {len(strategy_total)}, Сделок: {len(rows)}")
        for strategy in strategy_total:
            logger.info(f"   {strategy}: тейк через {self.avg_time_to_tp.get(strategy, '?')}ч, "
                       f"стоп через {self.avg_time_to_sl.get(strategy, '?')}ч, "
                       f"вероятность тейка: {self.tp_probability.get(strategy, '?')}%")

    def predict(self, signal: Dict) -> Dict:
        """Предсказание времени для сигнала."""
        strategy = signal.get('strategy', 'unknown')

        # Если нет данных — используем время в зависимости от таймфрейма
        if not self.is_trained or strategy not in self.avg_time_to_tp:
            timeframe = signal.get('timeframe', '15m')
            if timeframe == '5m':
                time_tp, time_sl = 0.5, 0.3
            elif timeframe == '15m':
                time_tp, time_sl = 2.0, 1.0
            elif timeframe == '1h':
                time_tp, time_sl = 6.0, 3.0
            else:
                time_tp, time_sl = 4.0, 2.0
            return {
                'time_to_tp': time_tp,
                'time_to_sl': time_sl,
                'tp_probability': 50.0,
                'best_entry': 'сейчас',
                'expected_profit_time': f'через ~{time_tp}ч',
            }

        time_to_tp = self.avg_time_to_tp.get(strategy, 2.0)
        time_to_sl = self.avg_time_to_sl.get(strategy, 1.0)
        tp_prob = self.tp_probability.get(strategy, 50.0)

        # Корректировка на основе уверенности
        confidence = signal.get('confidence', 0.5)
        if confidence > 0.70:
            time_to_tp *= 0.8  # Быстрее
            tp_prob += 10
        elif confidence < 0.50:
            time_to_tp *= 1.3  # Медленнее
            tp_prob -= 10

        tp_prob = max(20, min(90, tp_prob))

        return {
            'time_to_tp': round(time_to_tp, 1),
            'time_to_sl': round(time_to_sl, 1),
            'tp_probability': round(tp_prob, 1),
            'best_entry': 'сейчас',
            'expected_profit_time': f'Тейк через ~{time_to_tp:.1f}ч ({tp_prob:.0f}%)',
        }

    def get_summary(self, signal: Dict) -> str:
        """Краткий прогноз для сигнала."""
        pred = self.predict(signal)

        tp_h = pred['time_to_tp']
        sl_h = pred['time_to_sl']
        tp_p = pred['tp_probability']

        # Разное время для разных стратегий
        if tp_p >= 60:
            outlook = "👍 Высокая вероятность тейка"
        elif tp_p >= 45:
            outlook = "👌 Средняя вероятность"
        else:
            outlook = "⚠️ Рискованно"

        return (
            f"🎯 Тейк через ~{tp_h:.1f}ч ({tp_p:.0f}%)\n"
            f"⚠️ Стоп через ~{sl_h:.1f}ч\n"
            f"{outlook}"
        )