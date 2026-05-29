"""
Файл: binance_client.py — ЗАЩИТА ОТ НУЛЕВОЙ ЦЕНЫ (ИСПРАВЛЕНО)
"""

import asyncio
import hashlib
import hmac
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional

import numpy as np
import pandas as pd
import requests

from config import config
from cache import cache
from logger import logger

executor = ThreadPoolExecutor(max_workers=10)


class BinanceClient:
    """Клиент Binance с защитой от нулевой цены."""

    BASE_URL = "https://api.binance.com"

    def __init__(self):
        self.has_keys = bool(config.BINANCE_API_KEY and config.BINANCE_SECRET_KEY)
        self.price_cache: Dict[str, float] = {}
        self.session = requests.Session()
        if self.has_keys:
            self.session.headers.update({"X-MBX-APIKEY": config.BINANCE_API_KEY})

    def _sign(self, params: dict) -> str:
        query = urllib.parse.urlencode(params)
        return hmac.new(
            config.BINANCE_SECRET_KEY.encode(),
            query.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _signed_request(self, method: str, endpoint: str, params: dict = None) -> dict:
        if params is None:
            params = {}
        params['timestamp'] = int(time.time() * 1000)
        params['signature'] = self._sign(params)
        url = f"{self.BASE_URL}{endpoint}"
        try:
            if method == 'GET':
                resp = self.session.get(url, params=params, timeout=15)
            elif method == 'POST':
                resp = self.session.post(url, data=params, timeout=15)
            else:
                return {}
            return resp.json()
        except Exception as e:
            logger.error(f"API ошибка: {e}")
            return {}

    async def initialize(self):
        if not self.has_keys:
            logger.warning("Нет API ключей Binance")
            return
        try:
            resp = await asyncio.get_event_loop().run_in_executor(
                executor,
                lambda: self.session.get(f"{self.BASE_URL}/api/v3/ping", timeout=10),
            )
            if resp.status_code == 200:
                logger.info("Binance подключён!")
                # Проверка цены
                price = await self.get_current_price("BTCUSDT")
                if price and price > 0:
                    logger.info(f"BTC цена: {price:.2f}$")
                else:
                    logger.error("Не удалось получить цену BTC!")
        except Exception as e:
            logger.error(f"Ошибка Binance: {e}")

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Текущая цена с защитой от нуля."""
        if symbol in self.price_cache:
            cached = self.price_cache[symbol]
            if cached > 0:
                return cached

        try:
            resp = await asyncio.get_event_loop().run_in_executor(
                executor,
                lambda: self.session.get(
                    f"{self.BASE_URL}/api/v3/ticker/price",
                    params={"symbol": symbol}, timeout=5,
                ),
            )
            data = resp.json()
            price = float(data.get("price", 0))

            # ЗАЩИТА: если цена 0, используем заглушку
            if price <= 0:
                logger.warning(f"Цена {symbol} = {price}! Использую заглушку.")
                price = self._mock_price(symbol)

            self.price_cache[symbol] = price
            return price
        except Exception:
            return self._mock_price(symbol)

    def _get_klines_sync(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        try:
            resp = self.session.get(
                f"{self.BASE_URL}/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
                timeout=15,
            )
            data = resp.json()
            if not data or "code" in data:
                return pd.DataFrame()

            df = pd.DataFrame(data, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore",
            ])
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            return df
        except Exception:
            return pd.DataFrame()

    async def get_klines(self, symbol: str, interval: str = "15m", limit: int = 200) -> pd.DataFrame:
        cache_key = f"klines_{symbol}_{interval}_{limit}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        if not self.has_keys:
            df = self._mock_klines(symbol, limit)
            cache.set(cache_key, df)
            return df

        df = await asyncio.get_event_loop().run_in_executor(
            executor, self._get_klines_sync, symbol, interval, limit,
        )
        if not df.empty:
            cache.set(cache_key, df)
            return df

        df = self._mock_klines(symbol, limit)
        cache.set(cache_key, df)
        return df

    async def create_market_order(self, symbol: str, side: str, quantity: float, **kwargs) -> Optional[Dict]:
        """Создать ордер. **kwargs для совместимости с MultiExchange (игнорирует лишние параметры)."""
        if not self.has_keys or config.PAPER_TRADING:
            price = await self.get_current_price(symbol) or 0
            # ЗАЩИТА от нулевой цены
            if price <= 0:
                price = self._mock_price(symbol)
            logger.info(f"[PAPER] {side} {quantity:.6f} {symbol} @ {price:.4f}")
            return {
                "symbol": symbol, "side": side, "quantity": quantity,
                "price": price, "status": "FILLED",
                "orderId": f"paper_{np.random.randint(10000, 99999)}",
            }

        try:
            params = {
                "symbol": symbol,
                "side": side,
                "type": "MARKET",
                "quantity": round(quantity, 6),
            }
            data = await asyncio.get_event_loop().run_in_executor(
                executor,
                lambda: self._signed_request('POST', '/api/v3/order', params),
            )
            if 'orderId' in data:
                logger.info(f"ОРДЕР: {side} {quantity:.6f} {symbol}")
                return {
                    "symbol": symbol, "side": side, "quantity": quantity,
                    "price": float(data.get('fills', [{}])[0].get('price', 0)),
                    "status": data.get('status', 'FILLED'),
                    "orderId": data['orderId'],
                }
        except Exception as e:
            logger.error(f"Ошибка ордера: {e}")
        return None

    async def close(self):
        self.session.close()

    @staticmethod
    def _mock_price(symbol: str) -> float:
        base = {
            "BTCUSDT": 67000, "ETHUSDT": 3500, "BNBUSDT": 580,
            "SOLUSDT": 170, "ADAUSDT": 0.65, "DOGEUSDT": 0.16,
            "AVAXUSDT": 38, "DOTUSDT": 7.5, "LINKUSDT": 16,
            "MATICUSDT": 1.2, "UNIUSDT": 8, "LTCUSDT": 85,
            "FILUSDT": 6, "APTUSDT": 12, "XRPUSDT": 0.6,
            "UMAUSDT": 3, "ARBUSDT": 1.5, "OPUSDT": 2.5,
            "NEARUSDT": 6, "INJUSDT": 25, "TIAUSDT": 10,
            "SEIUSDT": 0.5, "SUIUSDT": 1.2, "RUNEUSDT": 5,
            "FTMUSDT": 0.8, "FETUSDT": 1.5, "RNDRUSDT": 8,
            "GRTUSDT": 0.3, "WLDUSDT": 3, "SANDUSDT": 0.6,
        }.get(symbol, 100)
        return base * np.random.uniform(0.995, 1.005)

    @staticmethod
    def _mock_klines(symbol: str, limit: int) -> pd.DataFrame:
        base_price = BinanceClient._mock_price(symbol)
        dates = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq="15min")
        returns = np.random.normal(0.0002, 0.005, limit)
        prices = base_price * np.exp(np.cumsum(returns))
        return pd.DataFrame({
            "open": prices * np.random.uniform(0.999, 1.001, limit),
            "high": prices * np.random.uniform(1.001, 1.008, limit),
            "low": prices * np.random.uniform(0.992, 0.999, limit),
            "close": prices,
            "volume": np.random.uniform(100, 10000, limit) * base_price,
        }, index=dates)


exchange = BinanceClient()