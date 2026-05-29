import time

import redis

from app.core.config import settings


class RateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def _key(self, identifier: str, namespace: str = "login") -> str:
        minute = int(time.time() // 60)
        return f"rate:{namespace}:{identifier}:{minute}"

    def current_count(self, identifier: str, namespace: str = "login") -> int:
        return int(self.redis.get(self._key(identifier, namespace)) or 0)

    def check_and_increment(
        self, identifier: str, limit: int | None = None, *, namespace: str = "login"
    ) -> bool:
        max_requests = limit or settings.rate_limit_login_per_min
        key = self._key(identifier, namespace)
        count = self.redis.incr(key)
        if count == 1:
            self.redis.expire(key, 60)
        return count <= max_requests
