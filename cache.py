"""
Файл 4: cache.py
Простой in-memory кэш с TTL.
"""

import time
from typing import Any, Optional
from config import config


class SimpleCache:
    """Простой кэш в оперативной памяти."""

    def __init__(self, ttl: int = None):
        self.ttl = ttl or config.CACHE_TTL
        self._cache: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша."""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            del self._cache[key]
        return None

    def set(self, key: str, data: Any):
        """Сохранить значение в кэш."""
        self._cache[key] = (data, time.time())

    def delete(self, key: str):
        """Удалить значение."""
        self._cache.pop(key, None)

    def clear(self):
        """Очистить весь кэш."""
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)


cache = SimpleCache()