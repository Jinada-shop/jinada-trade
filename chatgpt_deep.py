"""
Файл: chatgpt_deep.py
Поддержка OpenAI + DeepSeek (работает в РФ/РБ)
"""

import json
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import requests

from config import config
from database import get_db
from logger import logger


class ChatGPTDeep:
    """
    AI анализатор рынка.
    Работает через OpenAI или DeepSeek (если OpenAI заблокирован).
    """

    def __init__(self, fetcher=None):
        self.fetcher = fetcher
        self.openai_key = getattr(config, 'OPENAI_API_KEY', '')
        self.deepseek_key = getattr(config, 'DEEPSEEK_API_KEY', '')

        # Определяем какой API использовать
        if self.deepseek_key:
            self.api_key = self.deepseek_key
            self.api_url = "https://api.deepseek.com/v1/chat/completions"
            self.api_name = "DeepSeek"
        elif self.openai_key:
            self.api_key = self.openai_key
            self.api_url = "https://api.openai.com/v1/chat/completions"
            self.api_name = "OpenAI"
        else:
            self.api_key = ""
            self.api_url = ""
            self.api_name = ""

        self.enabled = bool(self.api_key)
        self.session = requests.Session()

    # ================================================================
    async def analyze_market(self, symbols: list = None) -> str:
        """Главный метод: анализ рынка."""
        if not self.enabled:
            return self._local_analysis()

        if symbols is None:
            symbols = ["BTCUSDT", "ETHUSDT"]

        market_data = await self._collect_market_data(symbols)
        trade_data = self._collect_trade_data()

        if not market_data and "Нет данных" in trade_data:
            return self._local_analysis()

        prompt = self._build_prompt(market_data, trade_data)

        try:
            resp = self.session.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat" if self.deepseek_key else "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.7,
                },
                timeout=30,
            )
            data = resp.json()

            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content']
            else:
                logger.error(f"{self.api_name} ответ: {data}")
                return self._local_analysis()
        except Exception as e:
            logger.error(f"{self.api_name} ошибка: {e}")
            return self._local_analysis()

    # ================================================================
    async def analyze_trades(self) -> str:
        """Анализ только сделок."""
        if not self.enabled:
            return self._local_analysis()

        trade_data = self._collect_trade_data()

        prompt = f"""
        Я — торговый бот. Проанализируй мои последние сделки и дай рекомендации.

        {trade_data}

        Ответь кратко (3-5 пунктов) на русском.
        """

        try:
            resp = self.session.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "deepseek-chat" if self.deepseek_key else "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 400,
                    "temperature": 0.7,
                },
                timeout=30,
            )
            data = resp.json()
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content']
            return self._local_analysis()
        except Exception:
            return self._local_analysis()

    # ================================================================
    async def predict_market(self, symbol: str = "BTCUSDT") -> str:
        """Прогноз на 24 часа."""
        if not self.enabled or not self.fetcher:
            return f"Прогноз для {symbol}: нет данных"

        df = await self.fetcher(symbol, "1h", 200)
        if df.empty:
            return f"Прогноз для {symbol}: нет данных"

        current_price = df['close'].iloc[-1]
        change_24h = (df['close'].iloc[-1] / df['close'].iloc[-24] - 1) * 100 if len(df) >= 24 else 0
        high_200 = df['high'].max()
        low_200 = df['low'].min()
        volatility = df['close'].pct_change().std() * 100

        prompt = f"""
        Дай краткий прогноз для {symbol} на 24 часа.
        Текущая цена: {current_price:.2f}
        Изменение за 24ч: {change_24h:+.1f}%
        Максимум за 200ч: {high_200:.2f}
        Минимум за 200ч: {low_200:.2f}
        Волатильность: {volatility:.1f}%

        Ответь в формате:
        Направление: [вверх/вниз/боковик]
        Цель: [число]
        Уверенность: [%]
        """

        try:
            resp = self.session.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "deepseek-chat" if self.deepseek_key else "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.5,
                },
                timeout=20,
            )
            data = resp.json()
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content']
            return f"Прогноз для {symbol}: нейтрально"
        except Exception:
            return f"Прогноз для {symbol}: нейтрально"

    # ================================================================
    async def _collect_market_data(self, symbols: list) -> list:
        """Сбор рыночных данных."""
        market_data = []

        if not self.fetcher:
            return market_data

        for symbol in symbols[:10]:
            try:
                df = await self.fetcher(symbol, "1h", 200)
                if df.empty or len(df) < 24:
                    continue

                change_24h = (df['close'].iloc[-1] / df['close'].iloc[-24] - 1) * 100
                change_7d = (df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100
                volatility = df['close'].pct_change().std() * 100
                volume = df['volume'].iloc[-24:].mean() if len(df) >= 24 else df['volume'].mean()
                volume_now = df['volume'].iloc[-1]
                volume_change = (volume_now / volume - 1) * 100 if volume > 0 else 0

                market_data.append(
                    f"{symbol}: цена {df['close'].iloc[-1]:.2f}, "
                    f"24ч: {change_24h:+.1f}%, 7д: {change_7d:+.1f}%, "
                    f"вол: {volatility:.1f}%, об: {volume_change:+.0f}%"
                )
            except Exception as e:
                logger.error(f"Ошибка сбора данных {symbol}: {e}")

        return market_data

    # ================================================================
    def _collect_trade_data(self) -> str:
        """Сбор данных о сделках."""
        try:
            with get_db() as db:
                stats = db.execute(
                    "SELECT COUNT(*) as total, SUM(pnl) as pnl, "
                    "SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) as wins "
                    "FROM trades WHERE status='CLOSED'"
                ).fetchone()

                strategies = db.execute(
                    "SELECT strategy, COUNT(*) as trades, SUM(pnl) as pnl, "
                    "SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) as wins "
                    "FROM trades WHERE status='CLOSED' AND strategy != '' "
                    "GROUP BY strategy ORDER BY pnl DESC"
                ).fetchall()

                pairs = db.execute(
                    "SELECT symbol, COUNT(*) as trades, SUM(pnl) as pnl "
                    "FROM trades WHERE status='CLOSED' "
                    "GROUP BY symbol ORDER BY pnl DESC LIMIT 5"
                ).fetchall()

                recent = db.execute(
                    "SELECT symbol, direction, pnl, exit_reason, strategy "
                    "FROM trades WHERE status='CLOSED' "
                    "ORDER BY exit_time DESC LIMIT 10"
                ).fetchall()
        except Exception as e:
            logger.error(f"Ошибка БД: {e}")
            return "Нет данных о сделках"

        total = stats['total'] if stats and stats['total'] is not None else 0

        if total == 0:
            return "Нет завершённых сделок"

        text = f"Всего сделок: {total}\n"

        pnl = stats['pnl'] if stats and stats['pnl'] is not None else 0
        wins = stats['wins'] if stats and stats['wins'] is not None else 0
        win_rate = (wins / total * 100) if total > 0 else 0

        text += f"PnL: {pnl:+.2f}$\n"
        text += f"Винрейт: {win_rate:.0f}%\n"

        if strategies:
            text += "\nПо стратегиям:\n"
            for s in strategies:
                s_trades = s['trades'] if s['trades'] else 0
                s_wins = s['wins'] if s['wins'] else 0
                s_pnl = s['pnl'] if s['pnl'] else 0
                wr = (s_wins / s_trades * 100) if s_trades > 0 else 0
                text += f"  {s['strategy']}: {s_trades} сделок, {wr:.0f}%, {s_pnl:+.2f}$\n"

        if pairs:
            text += "\nТоп-5 пар:\n"
            for p in pairs:
                p_pnl = p['pnl'] if p['pnl'] else 0
                p_trades = p['trades'] if p['trades'] else 0
                text += f"  {p['symbol']}: {p_pnl:+.2f}$ ({p_trades} сделок)\n"

        if recent:
            text += "\nПоследние 10 сделок:\n"
            for r in recent:
                r_pnl = r['pnl'] if r['pnl'] else 0
                emoji = "🟢" if r_pnl > 0 else "🔴"
                text += f"  {emoji} {r['symbol']} {r['direction']}: {r_pnl:+.2f}$ ({r['exit_reason']})\n"

        return text

    # ================================================================
    def _build_prompt(self, market_data: list, trade_data: str) -> str:
        """Построение промпта."""
        market_text = "\n".join(market_data) if market_data else "Нет данных"

        return f"""
        Ты — профессиональный крипто-трейдер. Проанализируй рынок и сделки бота.

        📊 РЫНОК (200 часов истории):
        {market_text}

        📈 СДЕЛКИ БОТА:
        {trade_data}

        Дай КРАТКИЙ ответ (3-5 пунктов) на русском:
        1. Какие пары сейчас лучше всего торговать?
        2. Какие стратегии работают, какие нет?
        3. Какие настройки изменить (риск, стопы, тейки)?
        4. Прогноз на ближайшие 24 часа.

        Ответь кратко, без воды, только по делу.
        """

    # ================================================================
    def _local_analysis(self) -> str:
        """Локальный анализ без API ключа."""
        total = 0
        wins = 0
        pnl = 0.0
        best_name = "N/A"
        best_pnl = 0.0
        worst_name = "N/A"
        worst_pnl = 0.0
        strat_name = "N/A"
        strat_pnl = 0.0
        strat_trades = 0

        try:
            with get_db() as db:
                trades = db.execute(
                    "SELECT COUNT(*) as total, SUM(pnl) as pnl, "
                    "SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) as wins "
                    "FROM trades WHERE status='CLOSED'"
                ).fetchone()

                if trades:
                    total = trades['total'] or 0
                    pnl = trades['pnl'] or 0.0
                    wins = trades['wins'] or 0

                best_pair = db.execute(
                    "SELECT symbol, SUM(pnl) as pnl FROM trades WHERE status='CLOSED' "
                    "GROUP BY symbol ORDER BY pnl DESC LIMIT 1"
                ).fetchone()

                if best_pair:
                    best_name = best_pair['symbol'] or "N/A"
                    best_pnl = best_pair['pnl'] or 0.0

                worst_pair = db.execute(
                    "SELECT symbol, SUM(pnl) as pnl FROM trades WHERE status='CLOSED' "
                    "GROUP BY symbol ORDER BY pnl ASC LIMIT 1"
                ).fetchone()

                if worst_pair:
                    worst_name = worst_pair['symbol'] or "N/A"
                    worst_pnl = worst_pair['pnl'] or 0.0

                best_strat = db.execute(
                    "SELECT strategy, SUM(pnl) as pnl, COUNT(*) as trades "
                    "FROM trades WHERE status='CLOSED' AND strategy != '' "
                    "GROUP BY strategy ORDER BY pnl DESC LIMIT 1"
                ).fetchone()

                if best_strat:
                    strat_name = best_strat['strategy'] or "N/A"
                    strat_pnl = best_strat['pnl'] or 0.0
                    strat_trades = best_strat['trades'] or 0
        except Exception as e:
            logger.error(f"Ошибка local analysis: {e}")

        wr = (wins / total * 100) if total > 0 else 0

        lines = [
            "📊 Локальный анализ рынка",
            "━━━━━━━━━━━━━━━━━",
        ]

        if total > 0:
            lines += [
                f"🔹 Сделок всего: {total}",
                f"🔹 Винрейт: {wr:.0f}%",
                f"🔹 Общий PnL: {pnl:+.2f}$",
                f"🔹 Лучшая пара: {best_name} ({best_pnl:+.2f}$)",
                f"🔹 Худшая пара: {worst_name} ({worst_pnl:+.2f}$)",
                f"🔹 Лучшая стратегия: {strat_name} ({strat_pnl:+.2f}$, {strat_trades} сделок)",
            ]
        else:
            lines.append("🔹 Нет завершённых сделок")

        lines.append("━━━━━━━━━━━━━━━━━")
        lines.append("💡 Рекомендации:")

        if total > 0:
            lines += [
                f"1. Торговать: {best_name}",
                f"2. Исключить: {worst_name}",
                f"3. Стратегия: {strat_name}",
                f"4. Риск: {'уменьшить' if pnl < 0 else 'держать'} до 2-3%",
                f"5. Ждать STRONG сигналов от AI",
            ]
        else:
            lines += [
                "1. Накопить 50+ сделок для анализа",
                "2. Использовать Paper Trading",
                "3. Торговать только BTC и ETH",
                "4. Риск не более 2%",
            ]

        return "\n".join(lines)

    # ================================================================
    def close(self):
        """Закрыть сессию."""
        self.session.close()