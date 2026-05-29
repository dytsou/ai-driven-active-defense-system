import redis

from app.core.config import settings


class BlocklistManager:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def _key(self, ip: str) -> str:
        return f"block:ip:{ip}"

    def is_blocked(self, ip: str) -> bool:
        return bool(self.redis.exists(self._key(ip)))

    def block_ip(self, ip: str, ttl: int | None = None) -> None:
        self.redis.setex(self._key(ip), ttl or settings.ip_block_ttl_seconds, "1")
