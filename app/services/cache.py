"""Response caching.

The previous implementation required Redis and logged a connection timeout on every
startup because nothing was running on :6379. It degraded to no caching at all,
which is the worst outcome: the dependency's cost without its benefit.

This replaces it with an in-process TTL cache as the primary tier. For a
single-instance deployment -- which is what a free Render/Fly dyno is -- a local
dict is strictly faster than Redis, because it avoids serialisation and a network
hop. Redis remains available as an opt-in shared tier for multi-instance setups,
enabled only when ``REDIS_ENABLED`` is set, so the default path has no external
dependency and no error noise.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Optional

from app.config.settings import settings

logger = logging.getLogger(__name__)


class TTLCache:
    """Thread-safe LRU cache with per-entry expiry."""

    def __init__(self, max_entries: int = 2048, default_ttl: float = 300.0):
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None
            expires_at, value = entry
            if expires_at < now:
                del self._store[key]
                self.misses += 1
                return None
            self._store.move_to_end(key)
            self.hits += 1
            return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        expires_at = time.monotonic() + (ttl if ttl is not None else self.default_ttl)
        with self._lock:
            self._store[key] = (expires_at, value)
            self._store.move_to_end(key)
            while len(self._store) > self.max_entries:
                self._store.popitem(last=False)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> int:
        with self._lock:
            doomed = [key for key in self._store if key.startswith(prefix)]
            for key in doomed:
                del self._store[key]
            return len(doomed)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def stats(self) -> dict[str, Any]:
        total = self.hits + self.misses
        return {
            "entries": len(self._store),
            "max_entries": self.max_entries,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 4) if total else 0.0,
        }


class CacheService:
    """Local TTL cache, optionally mirrored into Redis."""

    def __init__(self) -> None:
        self.local = TTLCache(
            max_entries=4096,
            default_ttl=float(settings.CACHE_EXPIRE_SECONDS),
        )
        self._redis = None
        if getattr(settings, "REDIS_ENABLED", False):
            self._connect_redis()

    def _connect_redis(self) -> None:
        try:
            import redis

            client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                socket_timeout=1.0,
                socket_connect_timeout=1.0,
                decode_responses=True,
            )
            client.ping()
            self._redis = client
            logger.info("Redis cache tier enabled at %s:%s", settings.REDIS_HOST, settings.REDIS_PORT)
        except Exception as exc:  # noqa: BLE001 - any failure means "run local only"
            logger.info("Redis tier unavailable (%s); using in-process cache only", exc)
            self._redis = None

    def get(self, key: str) -> Optional[Any]:
        value = self.local.get(key)
        if value is not None:
            return value

        if self._redis is not None:
            try:
                raw = self._redis.get(key)
                if raw:
                    value = json.loads(raw)
                    self.local.set(key, value)
                    return value
            except Exception:  # noqa: BLE001
                self._redis = None
        return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        self.local.set(key, value, ttl)
        if self._redis is not None:
            try:
                self._redis.setex(key, int(ttl or settings.CACHE_EXPIRE_SECONDS), json.dumps(value))
            except Exception:  # noqa: BLE001
                self._redis = None

    def get_or_set(self, key: str, producer: Callable[[], Any], ttl: Optional[float] = None) -> Any:
        value = self.get(key)
        if value is not None:
            return value
        value = producer()
        self.set(key, value, ttl)
        return value

    def invalidate_user(self, user_id: int) -> None:
        """Drops every cached response derived from one user's taste profile."""
        self.local.invalidate_prefix(f"recs:{user_id}:")
        self.local.invalidate_prefix(f"feed:{user_id}:")
        if self._redis is not None:
            try:
                for pattern in (f"recs:{user_id}:*", f"feed:{user_id}:*"):
                    keys = list(self._redis.scan_iter(match=pattern, count=256))
                    if keys:
                        self._redis.delete(*keys)
            except Exception:  # noqa: BLE001
                self._redis = None

    def stats(self) -> dict[str, Any]:
        return {"local": self.local.stats(), "redis_enabled": self._redis is not None}


cache = CacheService()
