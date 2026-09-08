"""아기 정보 데이터베이스 조회와 저장을 담당합니다."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.baby import Baby


async def get_baby_by_id(
    session: AsyncSession,
    baby_id: str,
) -> Baby | None:
    """아기 ID로 아기 정보를 조회합니다."""
    result = await session.execute(
        select(Baby).where(Baby.id == baby_id)
    )

    return result.scalar_one_or_none()


async def get_baby_by_user_id(
    session: AsyncSession,
    user_id: str,
) -> Baby | None:
    """보호자 ID로 연결된 아기 정보를 조회합니다."""
    result = await session.execute(
        select(Baby).where(Baby.user_id == user_id)
    )

    return result.scalar_one_or_none()


async def create_baby(
    session: AsyncSession,
    baby: Baby,
) -> Baby:
    """새 아기 정보를 저장합니다."""
    session.add(baby)

    await session.flush()
    await session.refresh(baby)

    return baby


async def update_baby(
    session: AsyncSession,
    baby: Baby,
    update_data: dict,
) -> Baby:
    """전달받은 값만 아기 정보에 반영합니다."""
    for field_name, value in update_data.items():
        setattr(baby, field_name, value)

    await session.flush()
    await session.refresh(baby)

    return baby