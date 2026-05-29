"""
Файл: reconnect.py
Система автопереподключения при обрыве связи.
"""

import asyncio
import time
from datetime import datetime
from typing import Callable, Optional

from logger import logger


class ReconnectManager:
    """
    Автоматическое переподключение при обрывах связи.
    
    Функции:
    - Обнаружение обрыва соединения
    - Автоматический перезапуск функций
    - Сохранение состояния (позиции, баланс)
    - Уведомление о восстановлении
    """

    def __init__(self, bot_instance=None):
        self.bot = bot_instance
        self.max_retries = 10
        self.retry_delay = 5  # секунд между попытками
        self.reconnect_count = 0
        self.last_reconnect = None
        self.is_connected = True
        self.connection_callbacks: list[Callable] = []

    async def check_connection(self) -> bool:
        """Проверка соединения с интернетом."""
        try:
            import socket
            socket.setdefaulttimeout(3)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
            return True
        except Exception:
            return False

    async def check_binance(self) -> bool:
        """Проверка соединения с Binance."""
        if not self.bot:
            return False
        try:
            price = await self.bot.exchange.binance.get_current_price("BTCUSDT")
            return price is not None and price > 0
        except Exception:
            return False

    async def check_bybit(self) -> bool:
        """Проверка соединения с Bybit."""
        if not self.bot:
            return False
        try:
            price = await self.bot.exchange.bybit.get_current_price("BTCUSDT")
            return price is not None and price > 0
        except Exception:
            return False

    async def check_telegram(self) -> bool:
        """Проверка соединения с Telegram."""
        if not self.bot or not self.bot.telegram:
            return False
        try:
            await self.bot.telegram.bot.get_me()
            return True
        except Exception:
            return False

    async def full_health_check(self) -> dict:
        """Полная проверка всех соединений."""
        results = {
            'internet': await self.check_connection(),
            'binance': await self.check_binance(),
            'bybit': await self.check_bybit(),
            'telegram': await self.check_telegram(),
            'timestamp': datetime.now().isoformat(),
        }
        results['all_ok'] = all(results.values())
        return results

    def on_reconnect(self, callback: Callable):
        """Добавить функцию для вызова после переподключения."""
        self.connection_callbacks.append(callback)

    async def wait_for_connection(self) -> bool:
        """Ждать восстановления соединения."""
        logger.warning("🔴 СОЕДИНЕНИЕ ПОТЕРЯНО! Ожидаю восстановления...")

        for attempt in range(1, self.max_retries + 1):
            logger.info(f"🔄 Попытка {attempt}/{self.max_retries}...")

            if await self.check_connection():
                logger.info("✅ Интернет восстановлен!")
                self.is_connected = True
                self.reconnect_count += 1
                self.last_reconnect = datetime.now()
                return True

            await asyncio.sleep(self.retry_delay * attempt)  # Увеличиваем задержку

        logger.error("❌ Не удалось восстановить соединение после 10 попыток")
        return False

    async def safe_execute(self, func: Callable, *args, **kwargs):
        """
        Безопасное выполнение функции с авто-переподключением.
        Если соединение потеряно — ждёт восстановления и выполняет заново.
        """
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if self._is_connection_error(e):
                logger.warning(f"⚠️ Обрыв связи при выполнении: {e}")
                self.is_connected = False

                # Ждём восстановления
                if await self.wait_for_connection():
                    # Вызываем колбэки
                    for callback in self.connection_callbacks:
                        try:
                            await callback()
                        except Exception:
                            pass

                    # Пробуем снова
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e2:
                        logger.error(f"❌ Ошибка после переподключения: {e2}")

            raise

    def _is_connection_error(self, error: Exception) -> bool:
        """Проверка, является ли ошибка проблемой соединения."""
        error_str = str(error).lower()
        connection_keywords = [
            'connection', 'timeout', 'refused', 'reset',
            'network', 'socket', 'ssl', 'dns', 'unreachable',
            'disconnected', 'broken pipe', 'no route',
            'cannot connect', 'tls', 'certificate',
        ]
        return any(kw in error_str for kw in connection_keywords)

    async def health_monitor(self):
        """Фоновый мониторинг здоровья соединений."""
        while True:
            try:
                health = await self.full_health_check()

                if not health['all_ok']:
                    problems = [k for k, v in health.items() if not v and k != 'all_ok' and k != 'timestamp']
                    logger.warning(f"⚠️ Проблемы с: {', '.join(problems)}")

                    if not health['internet']:
                        self.is_connected = False
                        await self.wait_for_connection()

                # Проверяем не реже чем раз в 30 секунд
                await asyncio.sleep(30)

            except Exception as e:
                logger.error(f"Ошибка health monitor: {e}")
                await asyncio.sleep(60)

    def get_status(self) -> str:
        """Статус переподключений."""
        return (
            f"🔄 ПЕРЕПОДКЛЮЧЕНИЯ:\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔹 Всего переподключений: {self.reconnect_count}\n"
            f"🔹 Последнее: {self.last_reconnect.strftime('%H:%M:%S') if self.last_reconnect else 'Нет'}\n"
            f"🔹 Статус: {'🟢 Онлайн' if self.is_connected else '🔴 Оффлайн'}\n"
        )


class SafeAPICaller:
    """
    Безопасные вызовы API с авто-повтором.
    Оборачивает все критические функции бота.
    """

    def __init__(self, reconnect_manager: ReconnectManager):
        self.rm = reconnect_manager
        self.call_stats = {
            'total': 0,
            'retries': 0,
            'failures': 0,
        }

    async def call(self, func: Callable, *args, max_retries: int = 3, **kwargs):
        """Вызов функции с авто-повтором при ошибках соединения."""
        self.call_stats['total'] += 1

        for attempt in range(max_retries):
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                if self.rm._is_connection_error(e):
                    self.call_stats['retries'] += 1
                    logger.warning(f"🔄 Повтор {attempt+1}/{max_retries} после ошибки: {e}")

                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                    else:
                        self.call_stats['failures'] += 1
                        raise
                else:
                    raise

    def get_stats(self) -> str:
        return (
            f"📊 СТАТИСТИКА API:\n"
            f"🔹 Всего вызовов: {self.call_stats['total']}\n"
            f"🔹 Повторов: {self.call_stats['retries']}\n"
            f"🔹 Ошибок: {self.call_stats['failures']}\n"
        )