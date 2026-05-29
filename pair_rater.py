"""
Файл: pair_rater.py
Рейтинг пар по прибыльности.
"""

from database import get_db
from config import config
from logger import logger


class PairRater:
    """Управление парами на основе PnL."""

    def get_ratings(self):
        """Получить рейтинг всех пар."""
        with get_db() as db:
            rows = db.execute(
                "SELECT symbol, COUNT(*) as trades, SUM(pnl) as pnl "
                "FROM trades WHERE status='CLOSED' GROUP BY symbol ORDER BY pnl DESC"
            ).fetchall()

        return {r['symbol']: {'trades': r['trades'], 'pnl': r['pnl'] or 0} for r in rows}

    def get_best_pairs(self, top_n: int = 5):
        """Топ-N лучших пар."""
        ratings = self.get_ratings()
        sorted_pairs = sorted(ratings.items(), key=lambda x: x[1]['pnl'], reverse=True)
        return [s for s, _ in sorted_pairs[:top_n]]

    def remove_bad_pairs(self):
        """Удалить пары с большим минусом."""
        ratings = self.get_ratings()
        removed = []

        for sym, data in ratings.items():
            if data['pnl'] < config.MIN_PAIR_PNL and data['trades'] >= 5:
                if sym in config.SYMBOLS and sym not in ["BTCUSDT", "ETHUSDT"]:
                    config.SYMBOLS.remove(sym)
                    removed.append(sym)
                    logger.info(f"🔴 Пара удалена: {sym} (PnL: {data['pnl']:.0f}$)")

        return removed

    def get_status(self):
        """Статус рейтинга для Telegram."""
        ratings = self.get_ratings()
        text = "📊 РЕЙТИНГ ПАР:\n━━━━━━━━━━━━━━━━━━━━\n"

        sorted_pairs = sorted(ratings.items(), key=lambda x: x[1]['pnl'], reverse=True)
        for sym, data in sorted_pairs[:7]:
            emoji = "🟢" if data['pnl'] > 0 else "🔴" if data['pnl'] < 0 else "⚪"
            text += f"{emoji} {sym}: {data['pnl']:+.0f}$ ({data['trades']} сделок)\n"

        return text