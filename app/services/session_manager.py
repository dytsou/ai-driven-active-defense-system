import json
import uuid

import redis

SESSION_TTL_SECONDS = 3600


class SessionManager:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def create_session(self, user_id: str, username: str) -> str:
        session_id = str(uuid.uuid4())
        payload = json.dumps({"user_id": user_id, "username": username})
        self.redis.setex(self._key(session_id), SESSION_TTL_SECONDS, payload)
        return session_id

    def get_session(self, session_id: str) -> dict | None:
        raw = self.redis.get(self._key(session_id))
        if not raw:
            return None
        return json.loads(raw)

    def destroy_session(self, session_id: str) -> None:
        self.redis.delete(self._key(session_id))
