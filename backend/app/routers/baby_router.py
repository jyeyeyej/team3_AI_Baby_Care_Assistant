"""아기 정보 API를 제공합니다."""

from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.baby import (
    BabyCreateRequest,
    BabyResponse,
    BabyUpdateRequest,
)
from app.services.baby_service import (
    create_baby,
    get_baby,
    update_baby,
)
from app.services.auth_service import get_login_session


router = APIRouter(
    prefix="/api/babies",
    tags=["아기 정보"],
)


async def get_db_session(request: Request):
    """현재 FastAPI 앱의 PostgreSQL 세션을 제공합니다."""
    async with AsyncSession(
        request.app.state.db_engine,
        expire_on_commit=False,
    ) as session:
        yield session


async def get_authenticated_user(
    request: Request,
    x_user_id: str = Header(alias="X-User-Id"),
    x_session_id: str = Header(alias="X-Session-Id"),
) -> str:
    """Redis 로그인 세션을 확인하고 인증된 사용자 ID를 반환합니다."""
    login_session = await get_login_session(
        request.app.state.redis,
        x_user_id,
        x_session_id,
    )

    if login_session is None:
        raise HTTPException(
            status_code=401,
            detail="로그인 세션이 없거나 만료되었습니다.",
        )

    return login_session["user_id"]


def create_success_response(
    message: str,
    baby,
) -> dict:
    """프론트엔드 공통 성공 응답 형식을 만듭니다."""
    return {
        "success": True,
        "message": message,
        "data": BabyResponse.model_validate(baby),
        "request_id": str(uuid4()),
    }


@router.post("")
async def create_baby_api(
    baby_request: BabyCreateRequest,
    user_id: str = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """로그인한 테스트 사용자의 아기 정보를 등록합니다."""
    try:
        baby = await create_baby(
            session,
            user_id,
            baby_request,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return create_success_response(
        "아기 정보가 등록되었습니다.",
        baby,
    )


@router.get("/{baby_id}")
async def get_baby_api(
    baby_id: str,
    user_id: str = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """로그인한 테스트 사용자의 아기 정보를 조회합니다."""
    try:
        baby = await get_baby(
            session,
            user_id,
            baby_id,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    return create_success_response(
        "아기 정보를 조회했습니다.",
        baby,
    )


@router.patch("/{baby_id}")
async def update_baby_api(
    baby_id: str,
    baby_request: BabyUpdateRequest,
    user_id: str = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """로그인한 테스트 사용자의 아기 정보를 수정합니다."""
    try:
        baby = await update_baby(
            session,
            user_id,
            baby_id,
            baby_request,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=404 if "찾을 수 없습니다" in str(error) else 400,
            detail=str(error),
        ) from error

    return create_success_response(
        "아기 정보가 수정되었습니다.",
        baby,
    )
