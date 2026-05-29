"""
Файл: main.py — УМНОЕ УПРАВЛЕНИЕ + ГЛУБОКОЕ ПРОГНОЗИРОВАНИЕ ЦЕН
"""

import asyncio
import signal
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

from config import config
from logger import logger
from database import init_database, get_db
from multi_exchange import multi_exchange as exchange
from indicators import Indicators
from market_regime import MarketRegimeHMM
from sentiment import SentimentAnalyzer
from strategies import ScalpingStrategy, TrendStrategy, CounterTrendStrategy, GridStrategy
from risk_manager import RiskManager
from telegram_bot import TelegramBot
from chart_builder import ChartBuilder
from time_predictor import TimePredictor
from scanner import MarketScanner
from pnl_chart import PnLChart
from deep_ai_engine import DeepAIEngine
from chatgpt_deep import ChatGPTDeep
from smart_exit import SmartExit
from budget_manager import BudgetManager
from ai_companion import AICompanion
from reconnect import ReconnectManager, SafeAPICaller
from ultra_scalping import UltraScalping
from price_predictor import PricePredictor


class SuperTradingBot:
    def __init__(self):
        self.exchange = exchange
        self.deep_ai = DeepAIEngine(self._fetch)
        self.chatgpt_deep = ChatGPTDeep(self._fetch)
        self.deep_ai._load()

        self.risk_mgr = RiskManager(self.exchange)
        self.budget = BudgetManager()
        self.hmm = MarketRegimeHMM(4)
        self.sentiment = SentimentAnalyzer()
        self.chart = ChartBuilder()
        self.scanner = MarketScanner(self._fetch)
        self.pnl_chart = PnLChart()
        self.smart_exit = SmartExit()
        self.time_predictor = TimePredictor()
        self.ultra_scalping = UltraScalping(self.exchange)
        self.price_predictor = PricePredictor(self._fetch)

        self.reconnect = ReconnectManager(self)
        self.safe_api = SafeAPICaller(self.reconnect)
        self.companion: Optional[AICompanion] = None

        self.strategies = {
            "scalping": ScalpingStrategy(),
            "trend": TrendStrategy(),
            "counter_trend": CounterTrendStrategy(),
            "grid": GridStrategy(),
        }

        self.balance = self._load_balance()
        self.paused = False
        self.running = False
        self.open_positions: List[Dict] = []
        self.last_signals: Dict[str, datetime] = {}
        self.telegram: Optional[TelegramBot] = None
        self._scan_counter = 0
        self.daily_pnl = 0.0
        self.daily_start_balance = self.balance
        self.consecutive_losses = 0
        self.loss_pause_until: Optional[datetime] = None
        self.total_profit = 0.0
        self.daily_trades = 0
        self._last_us_notification = 0
        self.regime = {"state": 1, "state_name": "Неопределённый", "risk_multiplier": 1.0}
        self.last_trade_time: Optional[datetime] = None
        self._last_position_check = 0
        self._last_retrain_time: Optional[datetime] = None

    def _load_balance(self) -> float:
        balance_file = Path("balance.txt")
        try:
            if balance_file.exists():
                with open(balance_file, 'r') as f:
                    saved = float(f.read().strip())
                    if saved > 0:
                        logger.info(f"💰 Загружен баланс: {saved:.2f}$")
                        return saved
        except Exception:
            pass
        return config.INITIAL_BALANCE

    def _save_balance(self):
        try:
            with open("balance.txt", 'w') as f:
                f.write(f"{self.balance:.2f}")
        except Exception:
            pass

    def _load_open_positions(self):
        """Загрузка открытых позиций из БД при старте."""
        try:
            with get_db() as db:
                rows = db.execute("""
                    SELECT id, symbol, direction, entry_price, quantity, 
                           stop_loss, take_profit, strategy, entry_time
                    FROM trades 
                    WHERE status = 'OPEN'
                    ORDER BY entry_time ASC
                """).fetchall()

            loaded = 0
            frozen_total = 0.0
            
            for row in rows:
                quantity = row['quantity'] or 0
                entry_price = row['entry_price'] or 0
                total_spent = entry_price * quantity
                
                pos = {
                    'symbol': row['symbol'],
                    'type': 'BUY' if row['direction'] == 'LONG' else 'SELL',
                    'price': entry_price,
                    'quantity': quantity,
                    'stop_loss': row['stop_loss'],
                    'take_profit': row['take_profit'],
                    'strategy': row['strategy'] or 'unknown',
                    'partial_closed': False,
                    'trailing_active': False,
                    'entry_time': datetime.fromisoformat(row['entry_time'].replace('Z', '+00:00')) if row['entry_time'] else datetime.now(),
                    'db_id': row['id'],
                    'total_spent': total_spent,
                }
                
                self.open_positions.append(pos)
                frozen_total += total_spent
                loaded += 1
                logger.info(f"  📌 Загружена: {pos['symbol']} {pos['type']} "
                           f"@{pos['price']:.4f} x{pos['quantity']:.6f} = {total_spent:.2f}$")

            if loaded > 0:
                logger.info(f"📌 Загружено {loaded} открытых позиций")
                logger.info(f"💰 Баланс: {self.balance:.2f}$ | В позициях: {frozen_total:.2f}$ | Свободно: {self.balance - frozen_total:.2f}$")
            else:
                logger.info("📌 Открытых позиций нет")

        except Exception as e:
            logger.error(f"Ошибка загрузки позиций: {e}")

    async def _fetch(self, symbol, interval="15m", limit=200):
        return await self.safe_api.call(self.exchange.get_klines, symbol, interval, limit)

    async def _on_reconnect(self):
        logger.info("🔄 Восстановление...")
        if self.telegram and self.telegram.enabled:
            await self.telegram.send_alert("✅ Соединение восстановлено!")

    async def adaptive_risk_adjustment(self):
        """Адаптивная корректировка рисков на основе волатильности и режима рынка."""
        try:
            df_btc = await self._fetch("BTCUSDT", "1h", 50)
            if df_btc.empty:
                return

            volatility = df_btc['close'].pct_change().std() * 100
            self.regime = self.hmm.predict(df_btc)
            risk_mult = self.regime.get('risk_multiplier', 1.0)

            if volatility > 5:
                risk_mult *= 0.7
            elif volatility > 3:
                risk_mult *= 0.85
            elif volatility < 1.5:
                risk_mult *= 1.2
            elif volatility < 2.5:
                risk_mult *= 1.1

            self.risk_mgr.volatility_risk_mult = round(risk_mult, 2)

            if self._scan_counter % 120 == 0:
                logger.info(f"🔄 Адаптивный риск: x{risk_mult:.2f} | "
                           f"Вол-ть: {volatility:.1f}% | "
                           f"Режим: {self.regime.get('state_name')}")

        except Exception as e:
            logger.error(f"Ошибка адаптивного риска: {e}")

    async def auto_retrain_models(self):
        """Автоматическое переобучение всех моделей раз в 4 часа."""
        if self._last_retrain_time:
            elapsed = (datetime.now() - self._last_retrain_time).total_seconds()
            if elapsed < 14400:  # 4 часа
                return False
        
        logger.info("🔄 Авто-переобучение моделей...")
        
        try:
            # Переобучаем AI
            await self.deep_ai.train_on_history(config.SYMBOLS, hours=500)
            
            # Переобучаем Price Predictor
            await self.price_predictor.train_all_pairs(config.SYMBOLS, history_hours=500)
            
            # Переобучаем HMM
            df_btc = await self._fetch("BTCUSDT", "1h", 500)
            if not df_btc.empty:
                self.hmm.fit(df_btc)
            
            # Переобучаем TimePredictor
            self.time_predictor.train()
            
            self._last_retrain_time = datetime.now()
            logger.info("✅ Все модели переобучены")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка переобучения: {e}")
            return False

    async def initialize(self):
        logger.info("=" * 60)
        logger.info("Super Trading Bot v4.0 — ГЛУБОКОЕ ПРОГНОЗИРОВАНИЕ + УМНОЕ УПРАВЛЕНИЕ")
        logger.info("=" * 60)

        init_database()
        self._load_open_positions()
        
        logger.info("✅ База данных готова")

        await self.exchange.initialize()
        self.daily_start_balance = self.balance
        
        with get_db() as db:
            today_pnl = db.execute(
                "SELECT SUM(pnl) FROM trades WHERE status='CLOSED' AND date(exit_time)=date('now')"
            ).fetchone()[0] or 0
            today_trades = db.execute(
                "SELECT COUNT(*) FROM trades WHERE status='CLOSED' AND date(exit_time)=date('now')"
            ).fetchone()[0] or 0
        
        self.daily_pnl = today_pnl
        self.daily_trades = today_trades
        
        logger.info(f"💰 Баланс: {self.balance:.2f}$ | ДЕМО")
        logger.info(f"📊 Сегодня: {self.daily_trades} сделок, PnL: {self.daily_pnl:+.2f}$")
        logger.info(f"📌 Открытых позиций: {len(self.open_positions)}")

        asyncio.create_task(self.reconnect.health_monitor())
        self.reconnect.on_reconnect(self._on_reconnect)

        # === ОБУЧЕНИЕ ВСЕХ МОДЕЛЕЙ ===
        logger.info("🧠 Обучение моделей на истории...")
        
        await self.deep_ai.train_on_history(config.SYMBOLS, hours=500)
        
        await self.price_predictor.train_all_pairs(config.SYMBOLS, history_hours=500)

        try:
            df_btc = await self._fetch("BTCUSDT", "1h", 500)
            if not df_btc.empty:
                self.hmm.fit(df_btc)
        except Exception:
            pass

        self.time_predictor.train()
        self._last_retrain_time = datetime.now()
        
        logger.info("✅ Все модели обучены!")

        self.telegram = TelegramBot(self)
        self.companion = AICompanion(self._fetch, self.telegram)
        self.running = True
        logger.info("✅ БОТ ГОТОВ!")
        logger.info("=" * 60)

    async def scan(self) -> List[Dict]:
        all_signals = []
        self._scan_counter += 1

        for symbol in config.SYMBOLS:
            try:
                df15m = await self._fetch(symbol, "15m", 200)
                if df15m.empty:
                    continue

                df15m = Indicators.add_all(df15m)
                last_15m = df15m.iloc[-1]

                # Получаем прогноз цены для этой пары
                price_pred = self.price_predictor.predictions.get(symbol, {})

                for s_name in config.ACTIVE_STRATEGIES:
                    strat = self.strategies.get(s_name)
                    if not strat:
                        continue

                    try:
                        timeframe = "1h" if s_name in ["trend", "grid"] else "15m"
                        if timeframe == "1h":
                            df_1h = await self._fetch(symbol, "1h", 200)
                            if df_1h.empty:
                                continue
                            df_1h = Indicators.add_all(df_1h)
                            signals = strat.analyze(df_1h, symbol, "1h")
                        else:
                            signals = strat.analyze(df15m, symbol, "15m")
                    except Exception:
                        continue

                    for sig in signals:
                        confidence = sig.get('confidence', 0.5)

                        # Корректировка от индикаторов
                        rsi = last_15m.get('RSI', 50)
                        if sig['type'] == 'BUY':
                            if rsi < 30: confidence += 0.12
                            elif rsi < 40: confidence += 0.08
                            elif rsi < 50: confidence += 0.04
                            else: confidence -= 0.04
                        else:
                            if rsi > 70: confidence += 0.12
                            elif rsi > 60: confidence += 0.08
                            elif rsi > 50: confidence += 0.04
                            else: confidence -= 0.04

                        adx = last_15m.get('ADX', 20)
                        if adx > 35: confidence += 0.08
                        elif adx > 25: confidence += 0.04
                        elif adx < 15: confidence -= 0.08

                        volume_ratio = last_15m.get('volume_ratio', 1)
                        if volume_ratio > 2.0: confidence += 0.08
                        elif volume_ratio > 1.5: confidence += 0.04
                        elif volume_ratio < 0.8: confidence -= 0.04

                        macd = last_15m.get('MACD', 0)
                        macd_signal = last_15m.get('MACD_signal', 0)
                        if sig['type'] == 'BUY' and macd > macd_signal: confidence += 0.04
                        if sig['type'] == 'SELL' and macd < macd_signal: confidence += 0.04

                        # Корректировка от режима рынка
                        regime_mult = self.regime.get('risk_multiplier', 1.0)
                        if regime_mult < 0.8:
                            confidence *= 0.85
                        elif regime_mult > 1.0:
                            confidence = min(0.95, confidence * 1.05)

                        # Корректировка от прогноза цены
                        if price_pred and 'predictions' in price_pred:
                            pred_4h = price_pred['predictions'].get('4h', {})
                            pred_dir = pred_4h.get('direction', '')
                            pred_conf = pred_4h.get('confidence', 50)
                            
                            if sig['type'] == 'BUY' and pred_dir == 'UP' and pred_conf > 50:
                                confidence += 0.08
                            elif sig['type'] == 'SELL' and pred_dir == 'DOWN' and pred_conf > 50:
                                confidence += 0.08
                            elif pred_conf < 40:
                                confidence *= 0.9

                        confidence = round(min(max(confidence, 0.25), 0.95), 2)
                        if confidence < 0.45:
                            continue

                        sig['confidence'] = confidence
                        sig['atr'] = last_15m.get('ATR', sig['price'] * 0.01)
                        sig['rsi'] = rsi
                        sig['adx'] = adx
                        sig['volume_ratio'] = volume_ratio

                        self._save_signal(sig)
                        all_signals.append(sig)

            except Exception as e:
                continue

        all_signals.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        return all_signals

    def _save_signal(self, sig: Dict):
        try:
            with get_db() as db:
                db.execute(
                    "INSERT INTO signals (symbol,signal_type,strategy,timeframe,price,rsi,volume_ratio,ml_confidence,hmm_state) VALUES (?,?,?,?,?,?,?,?,?)",
                    (sig["symbol"], sig["type"], sig.get("strategy", ""), sig.get("timeframe", "15m"),
                     sig["price"], sig.get("rsi", 50), sig.get("volume_ratio", 1),
                     sig.get("confidence", 0.5), self.regime.get('state', 0)),
                )
        except Exception:
            pass

    async def process(self, signals: List[Dict]):
        if self.loss_pause_until and datetime.now() < self.loss_pause_until:
            return

        # Кулдаун между сделками (60 секунд)
        if self.last_trade_time:
            elapsed = (datetime.now() - self.last_trade_time).total_seconds()
            if elapsed < 60:
                return

        for sig in signals:
            if len(self.open_positions) >= config.MAX_POSITIONS:
                break

            symbols_in_pos = [p['symbol'] for p in self.open_positions]
            if sig['symbol'] in symbols_in_pos:
                continue

            ai_result = self.deep_ai.predict(sig, self.regime)
            sig['ai_score'] = ai_result['ai_score']
            sig['ai_signal'] = ai_result['ai_signal']
            if ai_result['ai_signal'] == 'WEAK':
                continue

            if not self.risk_mgr.can_open_budget(self.balance, self.open_positions, ai_result['ai_signal']):
                continue

            time_pred = self.time_predictor.predict(sig)
            sig['time_summary'] = self.time_predictor.get_summary(sig)
            sig['exit_plan'] = self.smart_exit.get_plan(sig['price'], sig['type'])

            # Добавляем прогноз цены к сигналу
            if sig['symbol'] in self.price_predictor.predictions:
                sig['price_prediction'] = self.price_predictor.get_prediction_summary(sig['symbol'])

            if self.telegram and self.telegram.enabled:
                await self.telegram.send_signal(sig)

            if not self.paused and config.AUTO_TRADE:
                trade = await self.risk_mgr.execute(sig, self.balance, self.open_positions)
                if trade:
                    self.balance -= trade.get('total_spent', 0)
                    self.daily_trades += 1
                    trade['entry_time'] = datetime.now()
                    self._save_trade(trade)
                    self.open_positions.append(trade)
                    self._save_balance()
                    self.last_trade_time = datetime.now()

                    if self.telegram and self.telegram.enabled:
                        await self.telegram.send_trade_notification("open", {
                            'symbol': sig['symbol'],
                            'type': sig['type'],
                            'price': sig['price'],
                            'quantity': trade.get('quantity', 0),
                            'total_spent': trade.get('total_spent', 0),
                            'ai_signal': ai_result['ai_signal'],
                            'exchange': 'Binance',
                        })
                    
                    break

    def _save_trade(self, trade: Dict):
        try:
            with get_db() as db:
                db.execute(
                    "INSERT INTO trades (symbol,direction,entry_price,quantity,stop_loss,take_profit,status,strategy) VALUES (?,?,?,?,?,?,'OPEN',?)",
                    (trade["symbol"], "LONG" if trade["type"] == "BUY" else "SHORT",
                     trade["price"], trade.get("quantity", 0),
                     trade.get("stop_loss"), trade.get("take_profit"), trade.get("strategy", "")),
                )
        except Exception:
            pass

    async def manage_positions(self):
        """Умное управление позициями — с прогнозом цен."""
        self._last_position_check += 1
        
        for pos in self.open_positions[:]:
            try:
                price = await self.exchange.get_current_price(pos["symbol"])
                if not price:
                    continue

                if pos["type"] == "BUY":
                    pnl_pct = (price - pos['price']) / pos['price'] * 100
                else:
                    pnl_pct = (pos['price'] - price) / pos['price'] * 100

                # Стоп-лосс
                if pnl_pct <= -0.5:
                    await self._close(pos, price, "stop_loss")
                    continue

                # Тейк-профит
                if pnl_pct >= 0.5:
                    await self._close(pos, price, "take_profit")
                    continue

                # Частичное закрытие
                if pnl_pct >= 0.3 and not pos.get('partial_closed'):
                    qty = pos['quantity'] * 0.5
                    profit = (price - pos['price']) * qty if pos['type'] == 'BUY' else (pos['price'] - price) * qty
                    self.balance += price * qty
                    self.total_profit += profit
                    self.daily_pnl += profit
                    pos['quantity'] -= qty
                    pos['partial_closed'] = True
                    self._save_balance()
                    logger.info(f"📤 Частичное закрытие {pos['symbol']}: {qty:.6f} @ {price:.4f}, прибыль: {profit:+.2f}$")

                # Анализ прогноза (каждые 10 циклов)
                if self._last_position_check % 10 == 0:
                    df = await self._fetch(pos['symbol'], "15m", 50)
                    if df.empty:
                        continue
                    
                    df = Indicators.add_all(df)
                    last = df.iloc[-1]
                    
                    should_close = False
                    close_reasons = []
                    
                    # 1. RSI экстремум
                    rsi = last.get('RSI', 50)
                    if pos['type'] == 'BUY' and rsi > 75:
                        should_close = True
                        close_reasons.append(f"RSI перекуплен ({rsi:.0f})")
                    elif pos['type'] == 'SELL' and rsi < 25:
                        should_close = True
                        close_reasons.append(f"RSI перепродан ({rsi:.0f})")
                    
                    # 2. MACD разворот
                    if not should_close:
                        macd = last.get('MACD', 0)
                        macd_signal = last.get('MACD_signal', 0)
                        prev_macd = df['MACD'].iloc[-2]
                        prev_signal = df['MACD_signal'].iloc[-2]
                        
                        if pos['type'] == 'BUY' and prev_macd > prev_signal and macd <= macd_signal:
                            should_close = True
                            close_reasons.append("MACD разворот вниз")
                        elif pos['type'] == 'SELL' and prev_macd < prev_signal and macd >= macd_signal:
                            should_close = True
                            close_reasons.append("MACD разворот вверх")
                    
                    # 3. EMA пробой
                    if not should_close:
                        ema9 = last.get('EMA9', price)
                        ema21 = last.get('EMA21', price)
                        
                        if pos['type'] == 'BUY' and price < ema9 and price < ema21:
                            should_close = True
                            close_reasons.append("Пробой EMA9+EMA21 вниз")
                        elif pos['type'] == 'SELL' and price > ema9 and price > ema21:
                            should_close = True
                            close_reasons.append("Пробой EMA9+EMA21 вверх")
                    
                    # 4. Объёмный всплеск против позиции
                    if not should_close:
                        volume_ratio = last.get('volume_ratio', 1)
                        if volume_ratio > 3.0:
                            body = last.get('body', last['close'] - last['open'])
                            if pos['type'] == 'BUY' and body < 0 and abs(body) > last.get('ATR', 0.01):
                                should_close = True
                                close_reasons.append(f"Объёмный всплеск вниз x{volume_ratio:.1f}")
                            elif pos['type'] == 'SELL' and body > 0 and body > last.get('ATR', 0.01):
                                should_close = True
                                close_reasons.append(f"Объёмный всплеск вверх x{volume_ratio:.1f}")
                    
                    # 5. AI прогноз
                    if not should_close:
                        try:
                            sig = {
                                'symbol': pos['symbol'],
                                'type': pos['type'],
                                'price': price,
                                'rsi': rsi,
                                'volume_ratio': volume_ratio,
                                'adx': last.get('ADX', 20),
                                'macd': macd,
                                'macd_signal': macd_signal,
                                'atr_pct': last.get('ATR_pct', 1),
                                'bb_width': last.get('BB_width', 0.02),
                                'momentum': last.get('momentum', 0),
                                'body_pct': last.get('body_pct', 0) if 'body_pct' in last.index else 0,
                                'wick_ratio': 0,
                            }
                            ai_result = self.deep_ai.predict(sig, self.regime)
                            if ai_result['ai_signal'] == 'WEAK':
                                should_close = True
                                close_reasons.append(f"AI сигнал WEAK ({ai_result['ai_score']:.0%})")
                        except Exception:
                            pass
                    
                    # 6. Price Predictor прогноз
                    if not should_close:
                        should_hold, reason = self.price_predictor.should_reopen_position(
                            pos['symbol'], pos['type']
                        )
                        if not should_hold and pnl_pct > -0.1:
                            should_close = True
                            close_reasons.append(f"Прогноз: {reason}")
                    
                    # Закрываем если есть причины
                    if should_close:
                        if pnl_pct > -0.2:
                            await self._close(pos, price, f"predict: {' + '.join(close_reasons)}")
                            continue
                        elif 'entry_time' in pos:
                            hours = (datetime.now() - pos['entry_time']).total_seconds() / 3600
                            if hours > 2.0:
                                await self._close(pos, price, f"predict_loss: {' + '.join(close_reasons)}")
                                continue
                            else:
                                logger.info(f"🔍 {pos['symbol']}: негативный прогноз, но держим "
                                           f"(PnL: {pnl_pct:+.2f}%, прошло {hours:.1f}ч)")
                    
                    # Предупреждение если позиция висит больше 24 часов
                    if 'entry_time' in pos:
                        hours = (datetime.now() - pos['entry_time']).total_seconds() / 3600
                        if hours > 24:
                            logger.warning(f"⚠️ {pos['symbol']}: позиции больше 24ч! PnL: {pnl_pct:+.2f}%")

            except Exception as e:
                logger.error(f"Ошибка управления позицией {pos.get('symbol', '?')}: {e}")

    async def _close(self, pos: Dict, price: float, reason: str):
        if pos["type"] == "BUY":
            return_amount = price * pos.get("quantity", 0)
            total_spent = pos.get("total_spent", 0)
            pnl = return_amount - total_spent
        else:
            total_spent = pos.get("total_spent", 0)
            return_amount = price * pos.get("quantity", 0)
            pnl = total_spent - return_amount

        pnl = round(pnl, 2)
        self.balance += return_amount
        self.total_profit += pnl
        self.daily_pnl += pnl
        self._save_balance()

        if pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
                self.loss_pause_until = datetime.now() + timedelta(hours=config.LOSS_PAUSE_HOURS)
                self.consecutive_losses = 0
                if self.telegram and self.telegram.enabled:
                    await self.telegram.send_alert(
                        f"🛑 {config.MAX_CONSECUTIVE_LOSSES} убытка подряд! Пауза {config.LOSS_PAUSE_HOURS}ч"
                    )
        else:
            self.consecutive_losses = 0

        db_id = pos.get('db_id')
        if db_id:
            with get_db() as db:
                db.execute(
                    "UPDATE trades SET exit_price=?, pnl=?, status='CLOSED', exit_reason=?, exit_time=CURRENT_TIMESTAMP WHERE id=?",
                    (price, pnl, reason, db_id)
                )
        else:
            with get_db() as db:
                db.execute(
                    "UPDATE trades SET exit_price=?, pnl=?, status='CLOSED', exit_reason=?, exit_time=CURRENT_TIMESTAMP WHERE symbol=? AND status='OPEN' AND entry_price=?",
                    (price, pnl, reason, pos["symbol"], pos["price"])
                )

        self.open_positions.remove(pos)

        if self.telegram and self.telegram.enabled and abs(pnl) > 0.01:
            await self.telegram.send_trade_notification("close", {
                'symbol': pos['symbol'],
                'pnl': pnl,
                'balance': self.balance,
                'reason': reason,
            })

        logger.info(f"{'🟢' if pnl > 0 else '🔴'} Закрыта: {pos['symbol']} | PnL: {pnl:+.2f}$ | Баланс: {self.balance:.2f}$ | Причина: {reason}")

    async def run(self):
        await self.initialize()
        
        if self.telegram:
            self.telegram.start()

        if self.companion:
            await self.companion.market_update()

        if self.telegram and self.telegram.enabled:
            await self.telegram.send_message(
                f"🤖 БОТ ЗАПУЩЕН! v4.0\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Баланс: {self.balance:.2f}$\n"
                f"📌 Открыто позиций: {len(self.open_positions)}\n"
                f"📊 Сегодня: {self.daily_trades} сделок, {self.daily_pnl:+.2f}$\n"
                f"🧠 Прогноз цен: 500ч истории\n"
                f"📊 Стратегии: {len(self.strategies)}\n"
                f"🔄 Авто-переобучение: 4ч\n"
                f"🛡️ Лимит: 5% на сделку\n"
                f"⏱ Кулдаун: 60с\n"
                f"🕐 {datetime.now():%d.%m.%Y %H:%M}"
            )
        else:
            logger.warning("⚠️ Telegram не подключён!")

        scan_count = 0
        while self.running:
            try:
                if datetime.now().hour == 0 and self.daily_pnl != 0.0:
                    logger.info(f"🌅 Новый день! Вчера: {self.daily_trades} сделок, {self.daily_pnl:+.2f}$")
                    self.daily_pnl = 0.0
                    self.daily_trades = 0
                    self.daily_start_balance = self.balance
                    self.ultra_scalping.reset_daily()

                if not self.paused:
                    # Авто-переобучение раз в 4 часа
                    if scan_count % 480 == 0 and scan_count > 0:
                        await self.auto_retrain_models()
                    
                    # Адаптивный риск
                    if scan_count % 60 == 0:
                        await self.adaptive_risk_adjustment()

                    signals = await self.scan()
                    await self.process(signals)
                    scan_count += 1

                    # Проверка позиций
                    if scan_count % 5 == 0:
                        await self.manage_positions()

                    # Ultra Scalping
                    if scan_count % 3 == 0:
                        results = await self.ultra_scalping.scan_and_trade(self.balance)
                        for r in results:
                            self.total_profit += r['profit']
                            self.balance += r['profit']
                            self.daily_pnl += r['profit']
                            self._save_balance()

                        if self.telegram and self.telegram.enabled and self.ultra_scalping.total_trades > 0:
                            if self.ultra_scalping.total_trades - self._last_us_notification >= 50:
                                self._last_us_notification = self.ultra_scalping.total_trades
                                await self.telegram.send_trade_notification("ultra", {
                                    'symbol': 'BTC+ETH',
                                    'profit': self.ultra_scalping.total_profit,
                                    'total_trades': self.ultra_scalping.total_trades,
                                    'total_profit': self.ultra_scalping.total_profit,
                                })

                    if scan_count % 10 == 0:
                        us_stats = self.ultra_scalping.get_stats()
                        logger.info(f"📊 Скан #{scan_count}: {len(signals)} сигналов, "
                                   f"{len(self.open_positions)} позиций, {self.balance:.2f}$\n{us_stats}")

                await asyncio.sleep(config.SCAN_INTERVAL)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Ошибка: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def shutdown(self):
        logger.info("🛑 Завершение работы...")
        self.running = False
        
        logger.info(f"📌 {len(self.open_positions)} позиций сохранено в БД")
        
        await self.exchange.close()
        self._save_balance()
        
        if self.telegram and self.telegram.enabled:
            await self.telegram.send_alert(
                f"⏸ Бот остановлен\n"
                f"💰 Баланс: {self.balance:.2f}$\n"
                f"📌 Позиций: {len(self.open_positions)} (сохранены)"
            )
        
        logger.info(f"👋 Бот остановлен. Баланс: {self.balance:.2f}$")
        logger.info(f"📌 {len(self.open_positions)} позиций сохранено")


async def main():
    for d in ["models", "logs", "reports"]:
        Path(d).mkdir(exist_ok=True)

    bot = SuperTradingBot()

    def handler():
        asyncio.create_task(bot.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_event_loop().add_signal_handler(sig, handler)
        except NotImplementedError:
            pass

    try:
        await bot.run()
    except KeyboardInterrupt:
        pass
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("   SUPER TRADING BOT v4.0 — ГЛУБОКОЕ ПРОГНОЗИРОВАНИЕ")
    print("=" * 60 + "\n")
    asyncio.run(main())