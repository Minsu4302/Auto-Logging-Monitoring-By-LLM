import hashlib
import json
from typing import Any

import redis.asyncio as aioredis


class SemanticCache:
    """
    단순 해시 기반 캐시 (MVP).
    향후 embedding 벡터 유사도 검색으로 교체 예정.
    """

    def __init__(self, redis_url: str = "redis://redis:6379", ttl: int = 3600):
        self.redis_url = redis_url
        self.ttl = ttl
        self._client: aioredis.Redis | None = None

    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = await aioredis.from_url(self.redis_url, decode_responses=True)
        return self._client

    def _key(self, query: str) -> str:
        normalized = query.lower().strip()
        digest = hashlib.sha256(normalized.encode()).hexdigest()
        return f"semantic_cache:{digest}"

    async def get(self, query: str) -> Any | None:
        client = await self._get_client()
        cached = await client.get(self._key(query))
        if cached:
            return json.loads(cached)
        return None

    async def set(self, query: str, response: Any) -> None:
        client = await self._get_client()
        await client.setex(
            self._key(query),
            self.ttl,
            json.dumps(response, ensure_ascii=False),
        )

    async def invalidate(self, query: str) -> None:
        client = await self._get_client()
        await client.delete(self._key(query))
