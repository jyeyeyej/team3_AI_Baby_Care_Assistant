"""수유 알림 설정과 상태 변경 업무를 처리합니다."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reminder import ReminderSetting
from app.repositories.reminder_repository import (
    create_reminder,
    get_reminder_by_baby_id,
    get_reminder_by_id,
    update_reminder_interval,
)
from app.services.baby_service import get_baby


DEFAULT_FEEDING_INTERVAL_MINUTES = 180


async def get_feeding_reminder(
    session: AsyncSession,
    user_id: str,
    baby_id: str,
) -> ReminderSetting:
    """아기 소유권을 확인하고 수유 알림 설정을 조회합니다."""
    await get_baby(session, user_id, baby_id)

    reminder = await get_reminder_by_baby_id(session, baby_id)

    if reminder is not None:
        return reminder

    # 처음 조회하는 아기는 기본 3시간 간격 설정을 생성합니다.
    reminder = ReminderSetting(
        id=str(uuid4()),
        baby_id=baby_id,
        feeding_interval_minutes=DEFAULT_FEEDING_INTERVAL_MINUTES,
    )

    try:
        saved_reminder = await create_reminder(session, reminder)
        await session.commit()

        return saved_reminder
    except Exception:
        await session.rollback()
        raise


async def update_feeding_reminder(
    session: AsyncSession,
    user_id: str,
    reminder_id: str,
    feeding_interval_minutes: int,
) -> ReminderSetting:
    """로그인한 보호자가 소유한 수유 알림 간격을 수정합니다."""
    reminder = await get_reminder_by_id(session, reminder_id)

    if reminder is None:
        raise ValueError("수유 알림 설정을 찾을 수 없습니다.")

    await get_baby(session, user_id, reminder.baby_id)

    try:
        updated_reminder = await update_reminder_interval(
            session,
            reminder,
            feeding_interval_minutes,
        )
        await session.commit()

        return updated_reminder
    except Exception:
        await session.rollback()
        raise


async def change_reminder_action(
    session: AsyncSession,
    redis_client,
    user_id: str,
    reminder_id: str,
    action: str,
) -> dict:
    """알림 확인·다시 알림·건너뛰기 상태를 Redis에 저장합니다."""
    reminder = await get_reminder_by_id(session, reminder_id)

    if reminder is None:
        raise ValueError("수유 알림 설정을 찾을 수 없습니다.")

    await get_baby(session, user_id, reminder.baby_id)

    now = datetime.now(UTC)
    status_by_action = {
        "confirm": "confirmed",
        "snooze": "snoozed",
        "skip": "skipped",
    }

    next_reminder_at = None
    if action == "snooze":
        next_reminder_at = now + timedelta(minutes=10)
    elif action == "skip":
        next_reminder_at = now + timedelta(
            minutes=reminder.feeding_interval_minutes,
        )

    result = {
        "reminder_id": reminder.id,
        "baby_id": reminder.baby_id,
        "action": action,
        "status": status_by_action[action],
        "next_reminder_at": next_reminder_at.isoformat()
        if next_reminder_at is not None
        else None,
    }

    # 알림의 현재 상태는 하루 동안만 필요하므로 Redis에 보관합니다.
    redis_key = f"reminder:{user_id}:{reminder.baby_id}"
    await redis_client.set(
        redis_key,
        json.dumps(result, ensure_ascii=False),
        ex=60 * 60 * 24,
    )

    return result
