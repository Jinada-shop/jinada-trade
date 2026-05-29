"""
Файл: budget_manager.py
Умное распределение по силе сигнала.
"""

from typing import Dict, List

from config import config


class BudgetManager:
    """
    STRONG (AI >= 70%): до 40% от торгового лимита
    NEUTRAL (AI 50-70%): до 25% от торгового лимита
    WEAK (AI < 50%): до 15% от торгового лимита
    """

    def __init__(self):
        self.reserve_pct = 20.0
        self.max_in_trade_pct = 60.0

        self.signal_allocation = {
            'STRONG': 40.0,
            'NEUTRAL': 25.0,
            'WEAK': 15.0,
        }

    def get_position_limit(self, balance: float, ai_signal: str = 'NEUTRAL') -> float:
        max_trade = balance * (self.max_in_trade_pct / 100)
        alloc_pct = self.signal_allocation.get(ai_signal, 15.0)
        return max_trade * (alloc_pct / 100)

    def get_available(self, balance: float, open_positions: List[Dict],
                     ai_signal: str = 'NEUTRAL') -> float:
        reserve = balance * (self.reserve_pct / 100)
        in_trade = sum(p.get('total_spent', 0) for p in open_positions)
        max_trade = balance * (self.max_in_trade_pct / 100)
        pos_limit = self.get_position_limit(balance, ai_signal)

        available = min(
            balance - reserve - in_trade,
            max_trade - in_trade,
            pos_limit,
        )
        return max(0, available)

    def can_open_new(self, balance: float, open_positions: List[Dict],
                    ai_signal: str = 'NEUTRAL') -> bool:
        return self.get_available(balance, open_positions, ai_signal) >= config.MIN_ORDER_USDT

    def get_allocation_pct(self, ai_signal: str) -> float:
        return self.signal_allocation.get(ai_signal, 15.0)

    def get_status(self, balance: float, open_positions: List[Dict],
                  ai_signal: str = 'NEUTRAL') -> str:
        reserve = balance * (self.reserve_pct / 100)
        in_trade = sum(p.get('total_spent', 0) for p in open_positions)
        free = balance - reserve - in_trade
        available = self.get_available(balance, open_positions, ai_signal)
        alloc_pct = self.get_allocation_pct(ai_signal)

        pos_details = ""
        for i, p in enumerate(open_positions, 1):
            spent = p.get('total_spent', 0)
            pct = spent / balance * 100 if balance > 0 else 0
            pos_details += f"  {i}. {p['symbol']}: {spent:.0f}$ ({pct:.0f}%)\n"

        return (
            f"БЮДЖЕТ:\n"
            f"------------------------\n"
            f"Резерв: {reserve:.0f}$ (20%)\n"
            f"В сделках: {in_trade:.0f}$ ({len(open_positions)} поз.)\n"
            f"{pos_details}"
            f"Свободно: {free:.0f}$\n"
            f"Доступно ({ai_signal}): {available:.0f}$ ({alloc_pct:.0f}%)\n"
        )