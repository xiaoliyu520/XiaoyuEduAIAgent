import redis.asyncio as redis
from app.core.config import get_settings

settings = get_settings()

_redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis():
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


class SessionCache:
    def __init__(self, redis_client: redis.Redis, prefix: str = "session"):
        self.redis = redis_client
        self.prefix = prefix
        self.ttl = 3600

    def _key(self, conversation_id: int) -> str:
        return f"{self.prefix}:{conversation_id}"

    async def get_messages(self, conversation_id: int) -> list[dict]:
        data = await self.redis.get(self._key(conversation_id))
        if data is None:
            return []
        import json
        return json.loads(data)

    async def add_message(self, conversation_id: int, message: dict, max_window: int = 10):
        messages = await self.get_messages(conversation_id)
        messages.append(message)
        if len(messages) > max_window:
            messages = messages[-max_window:]
        import json
        await self.redis.set(self._key(conversation_id), json.dumps(messages, ensure_ascii=False), ex=self.ttl)

    async def clear(self, conversation_id: int):
        await self.redis.delete(self._key(conversation_id))


class HotQACache:
    def __init__(self, redis_client: redis.Redis, prefix: str = "hotqa"):
        self.redis = redis_client
        self.prefix = prefix
        self.ttl = 86400

    def _key(self, question_hash: str) -> str:
        return f"{self.prefix}:{question_hash}"

    async def get(self, question: str) -> str | None:
        import hashlib
        h = hashlib.md5(question.encode()).hexdigest()
        return await self.redis.get(self._key(h))

    async def set(self, question: str, answer: str):
        import hashlib
        h = hashlib.md5(question.encode()).hexdigest()
        await self.redis.set(self._key(h), answer, ex=self.ttl)
