import json
import time
from typing import Any


class MemoryRedis:
    def __init__(self):
        self._store: dict[str, tuple[str, float | None]] = {}

    def get(self, key: str):
        item = self._store.get(key)
        if not item:
            return None
        value, expire_at = item
        if expire_at and time.time() > expire_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        if nx and key in self._store:
            return False
        expire_at = time.time() + ex if ex else None
        self._store[key] = (value, expire_at)
        return True

    def setex(self, key: str, seconds: int, value: str):
        self._store[key] = (value, time.time() + seconds)

    def delete(self, key: str):
        self._store.pop(key, None)


_memory_redis = MemoryRedis()
_redis_client = None


def get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis

        client = redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1)
        client.ping()
        _redis_client = client
    except Exception:
        _redis_client = _memory_redis
    return _redis_client


from app.core.config import settings  # noqa: E402


def cache_get(key: str) -> Any | None:
    client = get_redis()
    value = client.get(key)
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def cache_set(key: str, value: Any, expire_seconds: int | None = None) -> None:
    client = get_redis()
    payload = json.dumps(value, default=str) if not isinstance(value, str) else value
    if expire_seconds:
        client.setex(key, expire_seconds, payload)
    else:
        client.set(key, payload)


def cache_delete(key: str) -> None:
    get_redis().delete(key)


class RedisLock:
    def __init__(self, key: str, expire: int = 5):
        self.key = key
        self.expire = expire
        self.acquired = False

    def __enter__(self):
        client = get_redis()
        if hasattr(client, "set"):
            self.acquired = bool(client.set(self.key, "1", nx=True, ex=self.expire))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.acquired:
            get_redis().delete(self.key)
