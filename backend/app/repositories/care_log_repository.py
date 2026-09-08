"""Read-only/owned-row helpers for the shared care_logs table."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.care_log import CareLog
from app.models.baby import Baby


async def get_by_id_for_user(session: AsyncSession, log_id: str, user_id: str) -> CareLog | None:
    result = await session.execute(
        select(CareLog).join(Baby, Baby.id == CareLog.baby_id).where(
            CareLog.id == log_id, Baby.user_id == user_id
        )
    )
    return result.scalar_one_or_none()
