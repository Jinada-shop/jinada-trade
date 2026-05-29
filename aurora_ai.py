"""
Файл: aurora_ai.py
AI Ассистент (аналог Aurora AI от Bybit)
"""

import json
from datetime import datetime
from typing import Dict, Optional

import numpy as np
import requests

from config import config
from database import get_db
from logger import logger


class AuroraAI:
    """AI Ассистент в стиле Aurora AI."""
    
    def __init__(self, fetcher=None):
        self.fetcher = fetcher
        self.api_key = getattr(config, 'OPENAI_API_KEY', '')
        self.use_api = bool(self.api_key)
    
    async def predict_price(self, symbol: str = "BTCUSDT") -> Dict:
        """Прогноз цены на 24 часа."""
        if not self.fetcher:
            return self._mock_prediction(symbol)
        
        df = await self.fetcher(symbol, "1h", 200)
        if df.empty:
            return self._mock_prediction(symbol)
        
        current_price = df['close'].iloc[-1]
        change_24h = (df['close'].iloc[-1] / df['close'].iloc[-24] - 1) * 100 if len(df) >= 24 else 0
        volatility = df['close'].pct_change().std() * 100
        high_200 = df['high'].max()
        low_200 = df['low'].min()
        
        up_target = current_price * (1 + volatility / 100 * 2)
        down_target = current_price * (1 - volatility / 100 * 2)
        
        sma20 = df['close'].rolling(20).mean().iloc[-1]
        sma50 = df['close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else sma20
        
        if current_price > sma20 > sma50:
            trend = "Бычий тренд"
            confidence = 65
        elif current_price < sma20 < sma50:
            trend = "Медвежий тренд"
            confidence = 65
        else:
            trend = "Боковик"
            confidence = 50
        
        if self.use_api:
            gpt_pred = await self._gpt_prediction(symbol, current_price, change_24h, volatility)
            if gpt_pred:
                return gpt_pred
        
        return {
            'symbol': symbol,
            'current_price': round(current_price, 2),
            'change_24h': round(change_24h, 1),
            'trend': trend,
            'confidence': confidence,
            'target_up': round(up_target, 2),
            'target_down': round(down_target, 2),
            'volatility': round(volatility, 1),
            'high_200': round(high_200, 2),
            'low_200': round(low_200, 2),
            'prediction': f"{trend}. Цель вверх: {up_target:.0f}$, вниз: {down_target:.0f}$",
            'timestamp': datetime.now().isoformat(),
        }
    
    async def _gpt_prediction(self, symbol, price, change, vol) -> Optional[Dict]:
        prompt = f"""
        Ты — AI ассистент для крипто-трейдинга.
        {symbol}: цена {price:.2f}$, 24ч: {change:+.1f}%, вол: {vol:.1f}%
        Дай КРАТКИЙ прогноз на 24 часа в JSON: {{"direction": "", "target": 0, "confidence": 0, "comment": ""}}
        """
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}], "max_tokens": 200, "temperature": 0.5},
                timeout=15,
            )
            content = resp.json()['choices'][0]['message']['content']
            return json.loads(content)
        except Exception:
            return None
    
    async def market_sentiment(self) -> Dict:
        """Анализ рыночного сентимента."""
        fear_greed = await self._get_fear_greed()
        
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
        sentiments = []
        
        if self.fetcher:
            for sym in symbols:
                df = await self.fetcher(sym, "1h", 24)
                if not df.empty and len(df) >= 24:
                    change = (df['close'].iloc[-1] / df['close'].iloc[-24] - 1) * 100
                    sentiments.append(change)
        
        avg_change = np.mean(sentiments) if sentiments else 0
        
        if avg_change > 2:
            market_sent = "Бычий"
        elif avg_change < -2:
            market_sent = "Медвежий"
        else:
            market_sent = "Нейтральный"
        
        return {
            'fear_greed': fear_greed,
            'avg_change_24h': round(avg_change, 1),
            'market_sentiment': market_sent,
            'recommendation': self._get_recommendation(fear_greed, market_sent),
            'timestamp': datetime.now().isoformat(),
        }
    
    async def _get_fear_greed(self) -> int:
        try:
            resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
            return int(resp.json()['data'][0]['value'])
        except Exception:
            return 50
    
    def _get_recommendation(self, fg: int, sent: str) -> str:
        if fg <= 25: return "Экстремальный страх. Возможен разворот вверх."
        elif fg <= 45: return "Страх. Ждать подтверждения разворота."
        elif fg <= 55: return "Нейтрально. Торговать по стратегии."
        elif fg <= 75: return "Жадность. Можно покупать, но осторожно."
        else: return "Экстремальная жадность. Возможна коррекция."
    
    async def chat_assistant(self, question: str) -> str:
        """AI Чат-ассистент."""
        with get_db() as db:
            total = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED'").fetchone()[0]
            pnl = db.execute("SELECT SUM(pnl) FROM trades WHERE status='CLOSED'").fetchone()[0] or 0
            wins = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED' AND pnl>0").fetchone()[0]
        
        wr = (wins / total * 100) if total > 0 else 0
        
        context = f"""
        Ты — AI ассистент торгового бота.
        Статистика: Сделок: {total}, Винрейт: {wr:.0f}%, PnL: {pnl:+.2f}$
        Ответь кратко: {question}
        """
        
        if self.use_api:
            try:
                resp = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": context}], "max_tokens": 300, "temperature": 0.7},
                    timeout=15,
                )
                return resp.json()['choices'][0]['message']['content']
            except Exception:
                pass
        
        return self._local_answer(question, total, wr, pnl)
    
    def _local_answer(self, q: str, total: int, wr: float, pnl: float) -> str:
        q = q.lower()
        if 'винрейт' in q: return f"Винрейт: {wr:.0f}% ({total} сделок)"
        if 'прибыль' in q or 'pnl' in q: return f"Прибыль: {pnl:+.2f}$ ({total} сделок)"
        if 'стратегия' in q: return "3 стратегии: Scalping, Trend, CounterTrend"
        if 'риск' in q: return f"Риск: {config.RISK_PER_TRADE_PCT}%, макс позиций: {config.MAX_POSITIONS}"
        if 'биржа' in q: return "Binance + Bybit (спот)"
        return "Я AI ассистент. Спросите о винрейте, прибыли, стратегиях, рисках или биржах."
    
    async def daily_report(self) -> str:
        """Ежедневный AI отчёт."""
        btc_pred = await self.predict_price("BTCUSDT")
        eth_pred = await self.predict_price("ETHUSDT")
        sentiment = await self.market_sentiment()
        
        with get_db() as db:
            today = db.execute(
                "SELECT COUNT(*), SUM(pnl) FROM trades WHERE status='CLOSED' AND date(exit_time)=date('now')"
            ).fetchone()
        
        return (
            "📊 AI ОТЧЁТ (Aurora Style)\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📈 BTC: {btc_pred['current_price']:.0f}$ | {btc_pred['trend']} | Цель: {btc_pred.get('target_up', 0):.0f}$\n"
            f"📈 ETH: {eth_pred['current_price']:.0f}$ | {eth_pred['trend']}\n\n"
            f"🧠 Сентимент: {sentiment['market_sentiment']} | Страх/Жадность: {sentiment['fear_greed']}\n"
            f"💡 {sentiment['recommendation']}\n\n"
            f"🤖 Бот сегодня: {today[0] or 0} сделок, PnL: {today[1] or 0:+.2f}$\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
    
    def _mock_prediction(self, symbol: str) -> Dict:
        return {
            'symbol': symbol, 'current_price': 77000, 'change_24h': 1.5,
            'trend': 'Бычий тренд', 'confidence': 65,
            'target_up': 78500, 'target_down': 75500, 'volatility': 2.5,
            'prediction': 'Бычий тренд. Цель вверх: 78500$, вниз: 75500$',
        }