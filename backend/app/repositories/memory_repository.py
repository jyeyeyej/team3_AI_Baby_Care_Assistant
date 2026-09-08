"""Repository for user-owned long-term preference memories."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user_memory import UserMemory


async def list_memories(session: AsyncSession, user_id: str) -> list[UserMemory]:
    result = await session.execute(
        select(UserMemory).where(UserMemory.user_id == user_id).order_by(UserMemory.updated_at.desc())
    )
    return list(result.scalars())


async def create_memory(session: AsyncSession, memory: UserMemory) -> UserMemory:
    session.add(memory)
    await session.flush()
    await session.refresh(memory)
    return memory
