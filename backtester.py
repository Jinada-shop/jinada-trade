"""
Файл 15: backtester.py
Движок бэктестинга.
"""

from typing import Dict

import numpy as np
import pandas as pd

from logger import logger


class Backtester:
    """Быстрый бэктест стратегии на исторических данных."""

    def __init__(self, initial_capital: float = 10_000):
        self.capital = initial_capital
        self.commission = 0.001
        self.slippage = 0.0005

    # ------------------------------------------------------------------
    async def run(self, df: pd.DataFrame, strategy) -> Dict:
        if len(df) < 100:
            return {}

        capital = self.capital
        position = None
        trades = []
        equity = [capital]

        for i in range(100, len(df)):
            current_price = df["close"].iloc[i]
            signals = strategy.analyze(df.iloc[: i + 1], "TEST", "1h")

            # Закрытие по стопу / тейку
            if position:
                if position["type"] == "BUY":
                    if current_price <= position["stop_loss"]:
                        pnl = (current_price - position["price"]) * position["qty"]
                        capital += pnl - position["qty"] * current_price * self.commission
                        trades.append({"pnl": pnl})
                        position = None
                    elif current_price >= position["take_profit"]:
                        pnl = (current_price - position["price"]) * position["qty"]
                        capital += pnl - position["qty"] * current_price * self.commission
                        trades.append({"pnl": pnl})
                        position = None

            # Вход
            if not position and signals:
                sig = signals[0]
                exec_price = current_price * (1 + self.slippage)
                qty = capital * 0.95 / exec_price
                position = {
                    "type": sig["type"],
                    "price": exec_price,
                    "qty": qty,
                    "stop_loss": sig.get("stop_loss", exec_price * 0.95),
                    "take_profit": sig.get("take_profit", exec_price * 1.05),
                }

            # Equity
            eq = capital
            if position:
                if position["type"] == "BUY":
                    eq += position["qty"] * current_price
                else:
                    eq += position["qty"] * (2 * position["price"] - current_price)
            equity.append(eq)

        if not trades:
            return {"total_return": 0, "sharpe": 0, "max_dd": 0, "trades": 0}

        pnls = [t["pnl"] for t in trades]
        win_rate = sum(1 for p in pnls if p > 0) / len(pnls)
        total_ret = (equity[-1] / equity[0] - 1) * 100

        rets = pd.Series(equity).pct_change().dropna()
        sharpe = (rets.mean() / rets.std()) * np.sqrt(365 * 24) if rets.std() > 0 else 0

        running_max = pd.Series(equity).expanding().max()
        drawdown = (pd.Series(equity) - running_max) / running_max
        max_dd = drawdown.min() * 100

        return {
            "total_return_pct": round(total_ret, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "win_rate_pct": round(win_rate * 100, 1),
            "total_trades": len(trades),
        }