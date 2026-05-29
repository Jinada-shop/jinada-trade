"""
Файл 2: logger.py
Настройка логирования.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

Path("logs").mkdir(exist_ok=True)


def setup_logger(name: str = "TradingBot") -> logging.Logger:
    """Создание и настройка логгера."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Консоль
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    console.setFormatter(console_fmt)

    # Файл с ротацией
    file_handler = RotatingFileHandler(
        "logs/bot.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s"
    )
    file_handler.setFormatter(file_fmt)

    logger.addHandler(console)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()