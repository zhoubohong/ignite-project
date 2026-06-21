"""L1 Session Memory — conversation context in Redis."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime

import redis.asyncio as aioredis

from app.core.config import settings


@dataclass
class ConversationTurn:
    role: str  # user | assistant | system
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class SessionMemory:
    """Redis-backed L1 memory for current conversation context (last N turns)."""

    def __init__(self, max_turns: int = 30) -> None:
        self.max_turns = max_turns
        self._redis: aioredis.Redis | None = None

    async def _ensure_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    def _key(self, session_id: uuid.UUID) -> str:
        return f"session:{session_id}:history"

    async def get_history(self, session_id: uuid.UUID) -> list[dict[str, str]]:
        r = await self._ensure_redis()
        raw = await r.lrange(self._key(session_id), 0, -1)
        return [json.loads(item) for item in raw]

    async def add_turn(
        self, session_id: uuid.UUID, role: str, content: str
    ) -> None:
        r = await self._ensure_redis()
        turn = ConversationTurn(role=role, content=content)
        key = self._key(session_id)
        await r.rpush(key, json.dumps(turn.__dict__))
        # Trim to max_turns
        length = await r.llen(key)
        if length > self.max_turns:
            await r.ltrim(key, length - self.max_turns, -1)
        await r.expire(key, 86400)  # 24h TTL

    async def clear(self, session_id: uuid.UUID) -> None:
        r = await self._ensure_redis()
        await r.delete(self._key(session_id))

    async def get_messages(
        self, session_id: uuid.UUID, system_prompt: str = ""
    ) -> list[dict[str, str]]:
        """Get full message list for LLM call, with optional system prompt."""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        history = await self.get_history(session_id)
        messages.extend(history)
        return messages


# Global instance
session_memory = SessionMemory()
