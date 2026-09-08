"""아기 정보 등록·조회·수정 업무를 처리합니다."""

from datetime import date
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.baby import Baby
from app.repositories.baby_repository import (
    create_baby as create_baby_record,
    get_baby_by_id,
    get_baby_by_user_id,
    update_baby as update_baby_record,
)
from app.schemas.baby import BabyCreateRequest, BabyUpdateRequest


def validate_birth_date(birth_date: date) -> None:
    """미래 생년월일이 입력되지 않았는지 확인합니다."""
    if birth_date > date.today():
        raise ValueError("생년월일은 미래 날짜로 설정할 수 없습니다.")


async def create_baby(
    session: AsyncSession,
    user_id: str,
    baby_request: BabyCreateRequest,
) -> Baby:
    """새 아기 정보를 등록합니다."""
    validate_birth_date(baby_request.birth_date)

    existing_baby = await get_baby_by_user_id(session, user_id)

    if existing_baby is not None:
        raise ValueError("이미 등록된 아기 정보가 있습니다.")

    baby = Baby(
        id=str(uuid4()),
        user_id=user_id,
        baby_name=baby_request.baby_name,
        birth_date=baby_request.birth_date,
        gender=baby_request.gender,
        current_weight_kg=baby_request.current_weight_kg,
        current_height_cm=baby_request.current_height_cm,
        feeding_type=baby_request.feeding_type,
        allergies=baby_request.allergies,
    )

    try:
        saved_baby = await create_baby_record(session, baby)
        await session.commit()

        return saved_baby
    except Exception:
        await session.rollback()
        raise


async def get_baby(
    session: AsyncSession,
    user_id: str,
    baby_id: str,
) -> Baby:
    """로그인한 보호자가 소유한 아기 정보를 조회합니다."""
    baby = await get_baby_by_id(session, baby_id)

    if baby is None or baby.user_id != user_id:
        raise ValueError("아기 정보를 찾을 수 없습니다.")

    return baby


async def update_baby(
    session: AsyncSession,
    user_id: str,
    baby_id: str,
    baby_request: BabyUpdateRequest,
) -> Baby:
    """로그인한 보호자가 소유한 아기 정보를 수정합니다."""
    baby = await get_baby(session, user_id, baby_id)

    update_data = baby_request.model_dump(exclude_unset=True)

    if "birth_date" in update_data:
        validate_birth_date(update_data["birth_date"])

    if not update_data:
        raise ValueError("수정할 정보를 입력해 주세요.")

    try:
        updated_baby = await update_baby_record(
            session,
            baby,
            update_data,
        )
        await session.commit()

        return updated_baby
    except Exception:
        await session.rollback()
        raise