"""
Файл: strategy_rotator.py
Автоматическая ротация стратегий по винрейту.
"""

from typing import Dict, List

from config import config
from database import get_db
from logger import logger


class StrategyRotator:
    """Выбирает лучшие стратегии на основе истории."""

    def __init__(self):
        self.strategies = config.ACTIVE_STRATEGIES.copy()
        self.performance: Dict[str, Dict] = {}

    def evaluate(self) -> Dict:
        """Оценка всех стратегий."""
        with get_db() as db:
            rows = db.execute("""
                SELECT strategy, COUNT(*) as total,
                       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                       SUM(pnl) as total_pnl
                FROM trades
                WHERE status = 'CLOSED'
                AND strategy != ''
                GROUP BY strategy
                ORDER BY total DESC
            """).fetchall()

        for row in rows:
            strategy = row['strategy']
            total = row['total'] or 1
            wins = row['wins'] or 0
            self.performance[strategy] = {
                'total': total,
                'wins': wins,
                'win_rate': wins / total * 100,
                'total_pnl': row['total_pnl'] or 0,
            }

        return self.performance

    def get_best_strategies(self, top_n: int = 3) -> List[str]:
        """Топ-N лучших стратегий."""
        perf = self.evaluate()

        # Фильтруем стратегии с минимум 10 сделками
        qualified = {
            s: p for s, p in perf.items()
            if p['total'] >= 10
        }

        if not qualified:
            return config.ACTIVE_STRATEGIES

        # Сортируем по винрейту
        sorted_strategies = sorted(
            qualified.items(),
            key=lambda x: x[1]['win_rate'],
            reverse=True,
        )

        best = [s[0] for s in sorted_strategies[:top_n]]

        logger.info(f"🔄 Лучшие стратегии: {best}")
        for s in sorted_strategies[:5]:
            logger.info(f"   {s[0]}: винрейт {s[1]['win_rate']:.0f}%, сделок {s[1]['total']}")

        return best

    def rotate(self):
        """Выполнить ротацию."""
        if not config.STRATEGY_ROTATION:
            return

        best = self.get_best_strategies(3)
        config.ACTIVE_STRATEGIES = best
        return best