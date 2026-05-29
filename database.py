"""
Файл 3: database.py
Работа с базой данных SQLite.
"""

import sqlite3
from contextlib import contextmanager
from config import config
from logger import logger


@contextmanager
def get_db():
    """Контекстный менеджер для подключения к БД."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_database():
    """Инициализация всех таблиц."""
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                strategy TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                price REAL NOT NULL,
                rsi REAL,
                volume_ratio REAL,
                ml_confidence REAL,
                hmm_state INTEGER,
                regime TEXT,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                quantity REAL,
                stop_loss REAL,
                take_profit REAL,
                status TEXT DEFAULT 'OPEN',
                pnl REAL,
                pnl_pct REAL,
                exit_reason TEXT,
                strategy TEXT,
                entry_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                exit_time DATETIME,
                FOREIGN KEY (signal_id) REFERENCES signals(id)
            );

            CREATE TABLE IF NOT EXISTS strategy_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT NOT NULL UNIQUE,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                win_rate REAL DEFAULT 0,
                profit_factor REAL DEFAULT 0,
                max_drawdown REAL DEFAULT 0,
                sharpe_ratio REAL DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ab_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_name TEXT NOT NULL,
                strategy TEXT NOT NULL,
                variant_a TEXT NOT NULL,
                variant_b TEXT NOT NULL,
                a_trades INTEGER DEFAULT 0,
                b_trades INTEGER DEFAULT 0,
                a_win_rate REAL DEFAULT 0,
                b_win_rate REAL DEFAULT 0,
                p_value REAL,
                winner TEXT,
                improvement_pct REAL,
                status TEXT DEFAULT 'running',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
            CREATE INDEX IF NOT EXISTS idx_signals_time ON signals(timestamp);
            CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
            CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
        """)
    logger.info("База данных инициализирована")