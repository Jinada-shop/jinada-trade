"""
Файл: config.py — БЫСТРЫЙ СТАРТ (ОПТИМИЗИРОВАНО ПОД ДЕМО)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv
load_dotenv()


@dataclass
class Config:
    # === Telegram ===
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    TELEGRAM_ADMIN_IDS: List[int] = field(default_factory=list)

    # === Биржи ===
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_SECRET_KEY: str = os.getenv("BINANCE_SECRET_KEY", "")
    BYBIT_API_KEY: str = os.getenv("BYBIT_API_KEY", "")
    BYBIT_SECRET_KEY: str = os.getenv("BYBIT_SECRET_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")

    # === ТОЛЬКО ПРИБЫЛЬНЫЕ ПАРЫ (по результатам 169 сделок) ===
    SYMBOLS: List[str] = field(default_factory=lambda: [
        "XRPUSDT",      # +401.55$
        "UNIUSDT",      # +68.00$
        "SOLUSDT",      # +16.13$
        "BTCUSDT",      # Базовая пара
        "ETHUSDT",      # Базовая пара
        "DOGEUSDT",     # Нейтрально (-0.70$)
    ])

    SCAN_INTERVAL: int = 30

    # === ТОЛЬКО ПРИБЫЛЬНЫЕ СТРАТЕГИИ ===
    ACTIVE_STRATEGIES: List[str] = field(default_factory=lambda: [
        "scalping",         # +146.75$ (111 сделок)
        "counter_trend",    # +654.63$ (8 сделок)
        "grid",             # Новая, нужен тест
    ])

    # === ДЕМО-ТОРГОВЛЯ ===
    AUTO_TRADE: bool = True
    PAPER_TRADING: bool = True
    INITIAL_BALANCE: float = 300.0

    # === БЕЗОПАСНЫЕ ЛИМИТЫ ===
    MAX_POSITIONS: int = 3               # Было 3 — снижено
    MAX_POSITION_HOURS: float = 3.0      # Было 4.0 — быстрее выход
    MIN_ORDER_USDT: float = 10.0
    RISK_PER_TRADE_PCT: float = 1.5      # Было 2.0 — меньше риск
    STOP_LOSS_ATR_MULT: float = 0.5
    TAKE_PROFIT_ATR_MULT: float = 1.5
    TRAILING_STOP_ACTIVATION: float = 0.5
    PARTIAL_EXIT_PCT: float = 50.0
    PARTIAL_EXIT_TARGET: float = 0.5

    # === ФИЛЬТРЫ (ОСЛАБЛЕНЫ ДЛЯ ДЕМО) ===
    ML_CONFIDENCE_THRESHOLD: float = 0.35
    MULTI_TF_CONFIRM: bool = False
    TREND_FILTER: bool = False
    MARKET_DIRECTION_FILTER: bool = False
    SPREAD_FILTER: bool = False

    # === ULTRA SCALPING (РЕАЛИСТИЧНЫЙ) ===
    ULTRA_SCALPING_ENABLED: bool = True
    ULTRA_SCALPING_BUDGET_PCT: float = 30.0    # Было 40% — меньше риск
    ULTRA_SCALPING_RISK_PCT: float = 5.0
    ULTRA_SCALPING_COOLDOWN: int = 1
    ULTRA_SCALPING_WAIT: int = 1
    ULTRA_SCALPING_MAX_DAILY_TRADES: int = 500  # Ограничение дневных сделок US
    ULTRA_SCALPING_MIN_ORDER: float = 3.0
    ULTRA_SCALPING_SYMBOLS: List[str] = field(default_factory=lambda: [
        "BTCUSDT", "ETHUSDT",
    ])

    # === ЛИМИТЫ ===
    AUTO_TUNING: bool = False
    ANOMALY_ALERT_PCT: float = 10.0
    PAIR_RATING_ENABLED: bool = False
    DAILY_TRADE_LIMIT: int = 20
    PNL_CHART_INTERVAL: int = 2
    WEEKDAY_FILTER: bool = False

    # === ЗАЩИТА КАПИТАЛА ===
    DAILY_LOSS_LIMIT_PCT: float = 8.0           # Было 10% — жёстче стоп
    MAX_CONSECUTIVE_LOSSES: int = 2              # Было 3 — быстрее пауза
    LOSS_PAUSE_HOURS: float = 2.0                # Было 1ч — дольше отдых
    DAILY_PROFIT_LOCK_PCT: float = 15.0

    SIGNAL_COOLDOWN: int = 120
    DATABASE_PATH: str = "trading_bot.db"
    CACHE_TTL: int = 30
    MODELS_DIR: Path = Path("models")
    API_PORT: int = 8000
    BALANCE_FILE: Path = Path("balance.txt")

    def __post_init__(self):
        for d in [self.MODELS_DIR, Path("logs"), Path("reports")]:
            d.mkdir(exist_ok=True)


config = Config()