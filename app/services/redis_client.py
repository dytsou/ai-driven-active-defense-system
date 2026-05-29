import uuid

import redis
from fastapi import Request

from app.core.config import settings

_redis_client: redis.Redis | None = None


def init_redis(url: str | None = None) -> redis.Redis:
    global _redis_client
    _redis_client = redis.from_url(url or settings.redis_url, decode_responses=True)
    return _redis_client


def get_redis() -> redis.Redis:
    if _redis_client is None:
        return init_redis()
    return _redis_client


def set_redis(client: redis.Redis) -> None:
    global _redis_client
    _redis_client = client


def get_redis_from_request(request: Request) -> redis.Redis:
    client = getattr(request.app.state, "redis", None)
    if client is not None:
        return client
    return get_redis()


def new_session_id() -> str:
    return str(uuid.uuid4())
