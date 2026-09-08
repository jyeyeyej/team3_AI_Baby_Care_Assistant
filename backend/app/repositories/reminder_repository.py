"""수유 알림 설정의 데이터베이스 조회와 저장을 담당합니다."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reminder import ReminderSetting


async def get_reminder_by_id(
    session: AsyncSession,
    reminder_id: str,
) -> ReminderSetting | None:
    """알림 설정 ID로 수유 알림 설정을 조회합니다."""
    result = await session.execute(
        select(ReminderSetting).where(ReminderSetting.id == reminder_id)
    )

    return result.scalar_one_or_none()


async def get_reminder_by_baby_id(
    session: AsyncSession,
    baby_id: str,
) -> ReminderSetting | None:
    """아기 ID로 연결된 수유 알림 설정을 조회합니다."""
    result = await session.execute(
        select(ReminderSetting).where(ReminderSetting.baby_id == baby_id)
    )

    return result.scalar_one_or_none()


async def create_reminder(
    session: AsyncSession,
    reminder: ReminderSetting,
) -> ReminderSetting:
    """새 수유 알림 설정을 저장합니다."""
    session.add(reminder)

    await session.flush()
    await session.refresh(reminder)

    return reminder


async def update_reminder_interval(
    session: AsyncSession,
    reminder: ReminderSetting,
    feeding_interval_minutes: int,
) -> ReminderSetting:
    """수유 알림 간격을 수정합니다."""
    reminder.feeding_interval_minutes = feeding_interval_minutes

    await session.flush()
    await session.refresh(reminder)

    return reminder
