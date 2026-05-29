"""
Файл: auto_tuner.py
Авто-тюнинг параметров на основе результатов.
"""

from database import get_db
from config import config
from logger import logger


class AutoTuner:
    """Автоматическая настройка параметров."""

    def analyze_and_tune(self):
        """Анализ сделок и корректировка параметров."""
        with get_db() as db:
            total = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED'").fetchone()[0]
            wins = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED' AND pnl>0").fetchone()[0]
            pnl = db.execute("SELECT SUM(pnl) FROM trades WHERE status='CLOSED'").fetchone()[0] or 0

        if total < 20:
            return "Недостаточно сделок для анализа"

        wr = (wins / total * 100) if total > 0 else 0
        changes = []

        # Винрейт < 40% — уменьшаем риск
        if wr < 40:
            old_risk = config.RISK_PER_TRADE_PCT
            config.RISK_PER_TRADE_PCT = max(0.5, old_risk * 0.7)
            changes.append(f"Риск: {old_risk:.1f}% → {config.RISK_PER_TRADE_PCT:.1f}%")

        # Винрейт > 55% — можно увеличить риск
        if wr > 55 and total > 50:
            old_risk = config.RISK_PER_TRADE_PCT
            config.RISK_PER_TRADE_PCT = min(10.0, old_risk * 1.2)
            changes.append(f"Риск: {old_risk:.1f}% → {config.RISK_PER_TRADE_PCT:.1f}%")

        # PnL отрицательный — шире стоп
        if pnl < 0 and total > 20:
            old_stop = config.STOP_LOSS_ATR_MULT
            config.STOP_LOSS_ATR_MULT = min(3.0, old_stop * 1.3)
            changes.append(f"Стоп ATR: {old_stop:.1f} → {config.STOP_LOSS_ATR_MULT:.1f}")

        # Много убытков подряд — уменьшаем позиции
        if wr < 35:
            old_max = config.MAX_POSITIONS
            config.MAX_POSITIONS = max(1, old_max - 1)
            changes.append(f"Макс позиций: {old_max} → {config.MAX_POSITIONS}")

        if changes:
            logger.info(f"🔧 АВТО-ТЮНИНГ: {', '.join(changes)}")
            return f"🔧 Изменено: {', '.join(changes)}"
        return "Параметры оптимальны"