"""Persistence and retrieval for safe answer-preference memories."""

import json

from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user_memory import UserMemory
from app.repositories.memory_repository import create_memory, list_memories
from .memory_safety_service import extract_safe_memory
from .memory_selector import select_memories

async def get_recent_conversation(redis, user_id: str, session_id: str) -> list[dict]:
    """Return the short-lived, user-scoped context used for the next answer."""
    raw_messages = await redis.lrange(f"chat:{user_id}:{session_id}", -8, -1)
    result = []
    for raw in raw_messages:
        try:
            item = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if item.get("role") in {"user", "assistant"} and isinstance(item.get("content"), str):
            result.append({"role": item["role"], "content": item["content"]})
    return result

async def get_relevant_memories(engine, user_id: str, question: str):
    async with AsyncSession(engine) as session:
        records = (await list_memories(session, user_id))[:20]
    return select_memories(records, question)

async def save_memory_candidate(engine, user_id: str, message: str) -> int:
    candidate = extract_safe_memory(message)
    if not candidate:
        return 0
    content, tags = candidate
    async with AsyncSession(engine) as session:
        existing = next((memory for memory in await list_memories(session, user_id) if memory.content == content), None)
        if existing is None:
            await create_memory(session, UserMemory(id=str(uuid4()), user_id=user_id, memory_type="preference", content=content, tags=tags))
            await session.commit()
            return 1
    return 0
