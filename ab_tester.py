"""
Файл 16: ab_tester.py
Система A/B-тестирования стратегий.
"""

import json
from datetime import datetime
from typing import Dict, List

import numpy as np
from scipy import stats

from database import get_db
from logger import logger


class ABTester:
    """Сравнение двух вариантов стратегии."""

    def __init__(self):
        self.active: Dict[str, Dict] = {}
        self.completed: List[Dict] = []

    # ------------------------------------------------------------------
    def create(self, name: str, strat_a: Dict, strat_b: Dict) -> str:
        test_id = f"ab_{name}_{datetime.now():%Y%m%d%H%M}"
        self.active[test_id] = {
            "name": name,
            "a_trades": [],
            "b_trades": [],
            "start": datetime.now(),
        }
        with get_db() as db:
            db.execute(
                "INSERT INTO ab_tests (test_name,strategy,variant_a,variant_b) "
                "VALUES (?,?,?,?)",
                (name, strat_a.get("name", ""), json.dumps(strat_a), json.dumps(strat_b)),
            )
        return test_id

    # ------------------------------------------------------------------
    def record(self, test_id: str, variant: str, result: Dict):
        if test_id not in self.active:
            return
        self.active[test_id][f"{variant}_trades"].append(result)
        self._maybe_finish(test_id)

    # ------------------------------------------------------------------
    def _maybe_finish(self, test_id: str):
        t = self.active[test_id]
        if len(t["a_trades"]) < 30 or len(t["b_trades"]) < 30:
            return

        a = [x.get("pnl_pct", 0) for x in t["a_trades"]]
        b = [x.get("pnl_pct", 0) for x in t["b_trades"]]

        a_win = sum(1 for v in a if v > 0) / len(a)
        b_win = sum(1 for v in b if v > 0) / len(b)

        _, p_val = stats.ttest_ind(a, b)
        improvement = (np.mean(b) - np.mean(a)) / abs(np.mean(a)) * 100 if np.mean(a) != 0 else 0

        winner = "B" if np.mean(b) > np.mean(a) and p_val < 0.05 else "A" if np.mean(a) > np.mean(b) and p_val < 0.05 else "inconclusive"

        result = {
            "test_id": test_id,
            "name": t["name"],
            "a_win_rate": a_win,
            "b_win_rate": b_win,
            "p_value": p_val,
            "winner": winner,
            "improvement_pct": improvement,
        }
        self.completed.append(result)
        del self.active[test_id]

        with get_db() as db:
            db.execute(
                "UPDATE ab_tests SET a_trades=?,b_trades=?,a_win_rate=?,b_win_rate=?,"
                "p_value=?,winner=?,improvement_pct=?,status='completed' WHERE test_name=?",
                (len(a), len(b), a_win, b_win, p_val, winner, improvement, t["name"]),
            )

        logger.info(f"A/B тест {t['name']}: winner={winner}, +{improvement:.1f}%")