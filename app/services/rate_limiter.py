import time

import redis

from app.core.config import settings


class RateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def _key(self, ip: str) -> str:
        minute = int(time.time() // 60)
        return f"rate:login:{ip}:{minute}"

    def check_and_increment(self, ip: str, limit: int | None = None) -> bool:
        max_requests = limit or settings.rate_limit_login_per_min
        key = self._key(ip)
        count = self.redis.incr(key)
        if count == 1:
            self.redis.expire(key, 60)
        return count <= max_requests
