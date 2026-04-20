import json
import redis.asyncio as redis
from app.core.config import get_settings

settings = get_settings()

_redis_client: redis.Redis | None = None
_redis_bytes_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def get_redis_bytes() -> redis.Redis:
    global _redis_bytes_client
    if _redis_bytes_client is None:
        _redis_bytes_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=False,
        )
    return _redis_bytes_client


async def close_redis():
    global _redis_client, _redis_bytes_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
    if _redis_bytes_client is not None:
        await _redis_bytes_client.close()
        _redis_bytes_client = None


class SessionCache:
    def __init__(self, redis_client: redis.Redis, prefix: str = "session"):
        self.redis = redis_client
        self.prefix = prefix
        self.ttl = 86400

    def _key(self, conversation_id: int) -> str:
        return f"{self.prefix}:{conversation_id}"

    async def get_messages(self, conversation_id: int) -> list[dict]:
        import json
        key = self._key(conversation_id)
        data = await self.redis.get(key)
        if data is not None:
            await self.redis.expire(key, self.ttl)
            return json.loads(data)
        return None

    async def set_messages(self, conversation_id: int, messages: list[dict], max_window: int = 50):
        import json
        if len(messages) > max_window:
            messages = messages[-max_window:]
        await self.redis.set(self._key(conversation_id), json.dumps(messages, ensure_ascii=False), ex=self.ttl)

    async def add_message(self, conversation_id: int, message: dict, max_window: int = 50):
        messages = await self.get_messages(conversation_id)
        if messages is None:
            messages = []
        messages.append(message)
        if len(messages) > max_window:
            messages = messages[-max_window:]
        import json
        await self.redis.set(self._key(conversation_id), json.dumps(messages, ensure_ascii=False), ex=self.ttl)

    async def refresh_ttl(self, conversation_id: int):
        key = self._key(conversation_id)
        exists = await self.redis.exists(key)
        if exists:
            await self.redis.expire(key, self.ttl)

    async def clear(self, conversation_id: int):
        await self.redis.delete(self._key(conversation_id))


class SummaryCache:
    def __init__(self, redis_client: redis.Redis, prefix: str = "summary"):
        self.redis = redis_client
        self.prefix = prefix
        self.ttl = 86400

    def _key(self, conversation_id: int) -> str:
        return f"{self.prefix}:{conversation_id}"

    async def get(self, conversation_id: int) -> tuple[str | None, int]:
        key = self._key(conversation_id)
        result = await self.redis.get(key)
        if result is not None:
            await self.redis.expire(key, self.ttl)
            data = json.loads(result)
            return data.get("summary"), data.get("message_count", 0)
        return None, 0

    async def set(self, conversation_id: int, summary: str, message_count: int):
        data = json.dumps({"summary": summary, "message_count": message_count})
        await self.redis.set(self._key(conversation_id), data, ex=self.ttl)

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
        key = self._key(h)
        result = await self.redis.get(key)
        if result is not None:
            await self.redis.expire(key, self.ttl)
        return result

    async def set(self, question: str, answer: str):
        import hashlib
        h = hashlib.md5(question.encode()).hexdigest()
        await self.redis.set(self._key(h), answer, ex=self.ttl)
