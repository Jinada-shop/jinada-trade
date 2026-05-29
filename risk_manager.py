"""
Файл: risk_manager.py — БЕЗОПАСНЫЙ (ЛИМИТ 5% НА СДЕЛКУ)
"""

from datetime import datetime
from typing import Dict, Optional, Tuple

from config import config
from budget_manager import BudgetManager
from logger import logger


class RiskManager:
    def __init__(self, exchange_client):
        self.exchange = exchange_client
        self.budget = BudgetManager()
        self.volatility_risk_mult = 1.0

    def position_size(self, balance: float, entry: float, stop: float,
                     open_positions: list = None,
                     ai_signal: str = 'NEUTRAL',
                     confidence: float = 0.5) -> float:
        if open_positions is None:
            open_positions = []

        max_for_position = self.budget.get_position_limit(balance, ai_signal)
        available = self.budget.get_available(balance, open_positions, ai_signal)
        max_spend = min(max_for_position, available)

        # === ЖЁСТКИЙ ЛИМИТ: НЕ БОЛЬШЕ 5% БАЛАНСА НА СДЕЛКУ ===
        max_spend = min(max_spend, balance * 0.05)
        
        if max_spend < config.MIN_ORDER_USDT:
            return 0.0

        risk_amount = max_spend * (config.RISK_PER_TRADE_PCT / 100)

        # Адаптивная корректировка от волатильности
        risk_amount *= self.volatility_risk_mult

        # Корректировка от уверенности AI
        if confidence >= 0.85:
            risk_amount *= 1.4
        elif confidence >= 0.70:
            risk_amount *= 1.2
        elif confidence >= 0.55:
            risk_amount *= 1.0
        elif confidence >= 0.40:
            risk_amount *= 0.7
        else:
            risk_amount *= 0.4

        risk_per_unit = abs(entry - stop)
        if risk_per_unit == 0:
            return 0.0

        size = risk_amount / risk_per_unit
        size = min(size, max_spend / entry)

        if size * entry < config.MIN_ORDER_USDT:
            return 0.0

        return round(size, 6)

    def can_open(self, open_positions: int) -> bool:
        return open_positions < config.MAX_POSITIONS

    def can_open_budget(self, balance: float, open_positions: list,
                       ai_signal: str = 'NEUTRAL') -> bool:
        return self.budget.can_open_new(balance, open_positions, ai_signal)

    def validate(self, signal: Dict, open_positions: int) -> Tuple[bool, str]:
        if not self.can_open(open_positions):
            return False, "Лимит позиций"
        if signal.get("confidence", 0) < 0.35:
            return False, "Низкая уверенность"
        if signal.get("anomaly_detected"):
            return False, "Аномалия"
        return True, "OK"

    def calculate_stop_loss(self, entry_price: float, atr: float,
                           direction: str = "BUY") -> float:
        mult = config.STOP_LOSS_ATR_MULT * self.volatility_risk_mult
        if direction == "BUY":
            return entry_price - atr * mult
        return entry_price + atr * mult

    def calculate_take_profit(self, entry_price: float, atr: float,
                             direction: str = "BUY") -> Tuple[float, float]:
        tp_mult = config.TAKE_PROFIT_ATR_MULT * self.volatility_risk_mult
        if direction == "BUY":
            partial = entry_price * (1 + config.PARTIAL_EXIT_TARGET / 100)
            full = entry_price + atr * tp_mult
        else:
            partial = entry_price * (1 - config.PARTIAL_EXIT_TARGET / 100)
            full = entry_price - atr * tp_mult
        return round(partial, 4), round(full, 4)

    async def execute(self, signal: Dict, balance: float,
                     open_positions: list = None,
                     exchange: str = "binance") -> Optional[Dict]:
        if open_positions is None:
            open_positions = []

        atr = signal.get("atr", signal["price"] * 0.01)
        ai_signal = signal.get("ai_signal", "NEUTRAL")
        confidence = signal.get("confidence", 0.5)

        stop_loss = signal.get("stop_loss")
        if not stop_loss:
            stop_loss = self.calculate_stop_loss(signal["price"], atr, signal["type"])

        take_profit = signal.get("take_profit")
        partial_tp = signal.get("take_profit_partial")
        if not take_profit or not partial_tp:
            partial_tp, take_profit = self.calculate_take_profit(signal["price"], atr, signal["type"])

        qty = self.position_size(balance, signal["price"], stop_loss, open_positions, ai_signal, confidence)

        if qty <= 0:
            return None

        total_cost = qty * signal["price"]

        # === ДВОЙНАЯ ЗАЩИТА: НЕ БОЛЬШЕ 5% БАЛАНСА ===
        max_allowed = balance * 0.05
        if total_cost > max_allowed:
            qty = max_allowed / signal["price"]
            total_cost = qty * signal["price"]
            logger.warning(f"⚠️ Позиция обрезана до 5% баланса: {total_cost:.2f}$")

        side = "BUY" if signal["type"] == "BUY" else "SELL"

        logger.info(f"Исполнение: {side} {qty:.6f} {signal['symbol']} @ {signal['price']:.4f} "
                   f"(всего: {total_cost:.2f}$, {total_cost/balance*100:.1f}% депозита, риск: x{self.volatility_risk_mult:.2f})")

        order = await self.exchange.create_order(
            symbol=signal["symbol"], side=side, quantity=qty, exchange=exchange
        )

        if order:
            return {
                **signal,
                "quantity": qty,
                "total_spent": round(total_cost, 2),
                "order_id": order.get("orderId") or order.get("order_id"),
                "stop_loss": round(stop_loss, 4),
                "take_profit": round(take_profit, 4),
                "take_profit_partial": round(partial_tp, 4),
                "partial_closed": False,
                "trailing_active": False,
                "entry_time": datetime.now(),
                "exchange": exchange,
            }
        return None