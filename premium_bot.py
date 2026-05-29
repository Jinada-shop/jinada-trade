"""
Файл: premium_bot.py
Монетизация: платный канал, подписки, копитрейдинг.
"""

import hashlib
import hmac
import time
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional

import requests

from config import config
from database import get_db
from logger import logger


class PremiumManager:
    """Управление подписками и копитрейдингом."""

    def __init__(self):
        self.subscribers: Dict[int, Dict] = {}  # user_id -> {expires, tier}
        self._load_subscribers()

    def _load_subscribers(self):
        with get_db() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    tier TEXT DEFAULT 'basic',
                    expires TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            rows = db.execute("SELECT * FROM subscribers WHERE expires > datetime('now')").fetchall()
            for r in rows:
                self.subscribers[r['user_id']] = {
                    'username': r['username'],
                    'tier': r['tier'],
                    'expires': r['expires'],
                }

    def is_premium(self, user_id: int) -> bool:
        return user_id in self.subscribers

    def add_subscriber(self, user_id: int, username: str, tier: str = 'basic', days: int = 30):
        from datetime import timedelta
        expires = (datetime.now() + timedelta(days=days)).isoformat()
        self.subscribers[user_id] = {'username': username, 'tier': tier, 'expires': expires}
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO subscribers (user_id, username, tier, expires) VALUES (?,?,?,?)",
                (user_id, username, tier, expires),
            )
        logger.info(f"💎 Подписчик добавлен: @{username} ({tier}) до {expires[:10]}")

    def get_signal_delay(self, user_id: int) -> int:
        """Задержка сигнала в секундах (0 для премиум, 300 для бесплатных)."""
        return 0 if self.is_premium(user_id) else 300


class CopyTrader:
    """Копитрейдинг: отправка сделок на второй аккаунт."""

    BASE_URL = "https://api.binance.com"

    def __init__(self):
        self.api_key = config.COPY_TRADING_API_KEY
        self.secret = config.COPY_TRADING_SECRET
        self.enabled = bool(self.api_key and self.secret)
        self.session = requests.Session()
        if self.enabled:
            self.session.headers.update({"X-MBX-APIKEY": self.api_key})

    def _sign(self, params: dict) -> str:
        query = urllib.parse.urlencode(params)
        return hmac.new(self.secret.encode(), query.encode(), hashlib.sha256).hexdigest()

    def copy_trade(self, symbol: str, side: str, quantity: float) -> Optional[Dict]:
        """Копировать сделку на второй аккаунт."""
        if not self.enabled:
            return None

        params = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'quantity': round(quantity, 6),
            'timestamp': int(time.time() * 1000),
        }
        params['signature'] = self._sign(params)

        try:
            resp = self.session.post(
                f"{self.BASE_URL}/api/v3/order",
                data=params,
                timeout=10,
            )
            data = resp.json()
            if 'orderId' in data:
                logger.info(f"📋 Копи-сделка: {side} {quantity} {symbol}")
                return data
            else:
                logger.error(f"Копи-ошибка: {data}")
        except Exception as e:
            logger.error(f"Копи-трейдинг ошибка: {e}")
        return None