"""
Файл: bybit_client.py
Клиент для Bybit (ИСПРАВЛЕНО).
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

from cache import cache
from logger import logger

executor = ThreadPoolExecutor(max_workers=10)


class BybitClient:
    """Клиент Bybit."""
    
    BASE_URL = "https://api.bybit.com"
    
    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.has_keys = bool(api_key and api_secret)
        self.session = requests.Session()
        self.price_cache: Dict[str, float] = {}
    
    def _sign(self, params: dict) -> str:
        query = urllib.parse.urlencode(sorted(params.items()))
        return hmac.new(
            self.api_secret.encode(),
            query.encode(),
            hashlib.sha256,
        ).hexdigest()
    
    def _request(self, method: str, endpoint: str, params: dict = None, signed: bool = False) -> dict:
        if params is None:
            params = {}
        
        if signed and self.has_keys:
            params['api_key'] = self.api_key
            params['timestamp'] = str(int(time.time() * 1000))
            params['sign'] = self._sign(params)
        
        url = f"{self.BASE_URL}{endpoint}"
        try:
            if method == 'GET':
                resp = self.session.get(url, params=params, timeout=10)
            else:
                resp = self.session.post(url, json=params, timeout=10)
            return resp.json()
        except Exception as e:
            logger.error(f"Bybit API ошибка: {e}")
            return {}
    
    async def initialize(self):
        if not self.has_keys:
            logger.warning("⚠️ Bybit: нет API ключей")
            return
        try:
            resp = self._request('GET', '/v5/market/time')
            if resp.get('retCode') == 0:
                logger.info("✅ Bybit подключён!")
        except Exception as e:
            logger.error(f"❌ Bybit ошибка: {e}")
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        if symbol in self.price_cache:
            return self.price_cache[symbol]
        
        try:
            resp = await asyncio.get_event_loop().run_in_executor(
                executor,
                lambda: self._request('GET', '/v5/market/tickers', {'category': 'spot', 'symbol': symbol}),
            )
            if resp.get('retCode') == 0 and resp.get('result', {}).get('list'):
                price = float(resp['result']['list'][0]['lastPrice'])
                self.price_cache[symbol] = price
                return price
        except Exception:
            pass
        return None
    
    async def get_klines(self, symbol: str, interval: str = "15", limit: int = 200) -> pd.DataFrame:
        cache_key = f"bybit_{symbol}_{interval}_{limit}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        
        interval_map = {"5m": "5", "15m": "15", "1h": "60", "4h": "240"}
        bybit_interval = interval_map.get(interval, "15")
        
        try:
            resp = await asyncio.get_event_loop().run_in_executor(
                executor,
                lambda: self._request('GET', '/v5/market/kline', {
                    'category': 'spot', 'symbol': symbol,
                    'interval': bybit_interval, 'limit': limit,
                }),
            )
            
            if resp.get('retCode') == 0 and resp.get('result', {}).get('list'):
                data = resp['result']['list']
                df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col])
                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
                df = df.iloc[::-1].set_index('timestamp')
                cache.set(cache_key, df)
                return df
        except Exception as e:
            logger.error(f"Bybit klines ошибка: {e}")
        
        return pd.DataFrame()
    
    async def create_market_order(self, symbol: str, side: str, quantity: float, **kwargs) -> Optional[Dict]:
        """Создать ордер. **kwargs для совместимости с MultiExchange."""
        if not self.has_keys:
            logger.info(f"[PAPER Bybit] {side} {quantity} {symbol}")
            return {"orderId": f"bybit_paper_{int(time.time())}", "status": "FILLED"}
        
        try:
            resp = await asyncio.get_event_loop().run_in_executor(
                executor,
                lambda: self._request('POST', '/v5/order/create', {
                    'category': 'spot', 'symbol': symbol,
                    'side': side, 'orderType': 'Market',
                    'qty': str(quantity),
                }, signed=True),
            )
            
            if resp.get('retCode') == 0:
                logger.info(f"✅ Bybit ордер: {side} {quantity} {symbol}")
                return resp.get('result', {})
            else:
                logger.error(f"❌ Bybit ордер ошибка: {resp.get('retMsg')}")
        except Exception as e:
            logger.error(f"❌ Bybit ордер: {e}")
        return None
    
    async def get_balance(self) -> Dict[str, float]:
        if not self.has_keys:
            return {"USDT": 0}
        
        try:
            resp = await asyncio.get_event_loop().run_in_executor(
                executor,
                lambda: self._request('GET', '/v5/account/wallet-balance', {
                    'accountType': 'UNIFIED',
                }, signed=True),
            )
            
            if resp.get('retCode') == 0:
                balances = {}
                for coin in resp.get('result', {}).get('list', [{}])[0].get('coin', []):
                    wallet = float(coin.get('walletBalance', 0))
                    if wallet > 0:
                        balances[coin['coin']] = wallet
                return balances
        except Exception:
            pass
        return {"USDT": 0}
    
    def close(self):
        self.session.close()