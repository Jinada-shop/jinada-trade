"""
Файл: pnl_chart.py
График PnL для отправки в канал.
"""

from datetime import datetime
from io import BytesIO

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

from database import get_db
from logger import logger


class PnLChart:
    """График прибыли."""

    @staticmethod
    def generate() -> BytesIO:
        """Создать график PnL."""
        with get_db() as db:
            rows = db.execute("""
                SELECT exit_time, pnl
                FROM trades
                WHERE status = 'CLOSED' AND pnl IS NOT NULL
                ORDER BY exit_time ASC
            """).fetchall()

        if not rows:
            return None

        times = [datetime.fromisoformat(r['exit_time']) for r in rows]
        pnls = [r['pnl'] for r in rows]
        cumulative = pd.Series(pnls).cumsum().values

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        # Кумулятивный PnL
        ax1.plot(times, cumulative, 'b-', linewidth=2)
        ax1.fill_between(times, 0, cumulative, where=(pd.Series(cumulative) >= 0), color='green', alpha=0.3)
        ax1.fill_between(times, 0, cumulative, where=(pd.Series(cumulative) < 0), color='red', alpha=0.3)
        ax1.set_title('Cumulative PnL (USDT)', fontsize=14)
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=0, color='black', linewidth=0.5)

        # Бары PnL
        colors = ['green' if p > 0 else 'red' for p in pnls[-20:]]
        ax2.bar(range(len(pnls[-20:])), pnls[-20:], color=colors)
        ax2.set_title('Last 20 Trades PnL', fontsize=14)
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color='black', linewidth=0.5)

        plt.tight_layout()
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)

        return buf

    @staticmethod
    def generate_summary() -> str:
        """Текстовый отчёт."""
        with get_db() as db:
            row = db.execute("""
                SELECT COUNT(*) total,
                       SUM(pnl) total_pnl,
                       AVG(pnl) avg_pnl,
                       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) wins
                FROM trades WHERE status = 'CLOSED'
            """).fetchone()

        total = row['total'] or 0
        win_rate = (row['wins'] / total * 100) if total > 0 else 0

        return (
            f"📊 <b>PnL ОТЧЁТ</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🔹 Сделок: {total}\n"
            f"🔹 Винрейт: {win_rate:.0f}%\n"
            f"🔹 Общий PnL: {row['total_pnl'] or 0:+.2f}$\n"
            f"🔹 Средний PnL: {row['avg_pnl'] or 0:+.2f}$\n"
            f"🕐 {datetime.now():%d.%m.%Y %H:%M}"
        )