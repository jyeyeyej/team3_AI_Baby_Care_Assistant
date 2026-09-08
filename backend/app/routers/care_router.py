"""수유 알림 설정 API를 제공합니다."""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.care import (
    CareLogCreateRequest,
    CareLogUpdateRequest,
    CareRecordsQuery,
    FeedingReminderResponse,
    ReminderActionRequest,
    ReminderActionResponse,
    ReminderSettingsUpdateRequest,
)
from app.services.auth_service import get_login_session
from app.services.care.care_log_service import (
    create_care_log,
    delete_care_log,
    get_care_logs,
    get_care_pattern,
    get_growth_records,
    update_care_log,
)
from app.services.care.reminder_service import (
    change_reminder_action,
    get_feeding_reminder,
    update_feeding_reminder,
)
from app.services.care.growth_service import build_growth_information


router = APIRouter(prefix="/api", tags=["육아 관리"])
logger = logging.getLogger(__name__)


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


def create_success_response(message: str, reminder) -> dict:
    """프론트엔드 공통 성공 응답 형식을 만듭니다."""
    return {
        "success": True,
        "message": message,
        "data": FeedingReminderResponse.model_validate(reminder),
        "request_id": str(uuid4()),
    }


def create_care_success_response(message: str, data: dict) -> dict:
    """Care MCP 결과를 프론트엔드 공통 성공 응답으로 변환합니다."""
    return {
        "success": True,
        "message": message,
        "data": data,
        "request_id": str(uuid4()),
    }


@router.get("/reminders/feeding/{baby_id}")
async def get_feeding_reminder_api(
    baby_id: str,
    user_id: str = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """수유 알림 간격을 조회하고 설정이 없으면 기본값을 생성합니다."""
    try:
        reminder = await get_feeding_reminder(
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
        "수유 알림 설정을 조회했습니다.",
        reminder,
    )


@router.patch("/reminders/{reminder_id}")
async def change_reminder_action_api(
    reminder_id: str,
    reminder_request: ReminderActionRequest,
    request: Request,
    user_id: str = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """수유 알림을 확인하거나 다시 알림·건너뛰기 상태로 변경합니다."""
    try:
        data = await change_reminder_action(
            session,
            request.app.state.redis,
            user_id,
            reminder_id,
            reminder_request.action,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    return {
        "success": True,
        "message": "수유 알림 상태를 변경했습니다.",
        "data": ReminderActionResponse.model_validate(data),
        "request_id": str(uuid4()),
    }


@router.patch("/reminders/feeding/{baby_id}/settings")
async def update_feeding_reminder_settings_api(
    baby_id: str,
    reminder_request: ReminderSettingsUpdateRequest,
    user_id: str = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """수유 알림 간격 설정을 수정합니다."""
    try:
        reminder = await get_feeding_reminder(session, user_id, baby_id)
        reminder = await update_feeding_reminder(
            session,
            user_id,
            reminder.id,
            reminder_request.feeding_interval_minutes,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    return create_success_response(
        "수유 알림 간격을 수정했습니다.",
        reminder,
    )


@router.post("/care-logs")
async def create_care_log_api(
    care_request: CareLogCreateRequest,
    user_id: str = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """UI 또는 텍스트로 입력한 육아 기록을 Care MCP에 저장합니다."""
    try:
        data = await create_care_log(
            session,
            user_id,
            care_request,
        )
    except ValueError as error:
        status_code = (
            409
            if care_request.input_source == "stt"
            and not care_request.confirmed_by_user
            else 400
        )
        raise HTTPException(
            status_code=status_code,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        # 개발 환경에서는 MCP가 반환한 실제 원인을 콘솔과 응답에 남긴다.
        # 원인이 확인되면 운영 환경에서는 일반 안내 문구로 바꿀 수 있다.
        logger.exception("Care MCP로 수유 기록을 저장하지 못했습니다.")
        raise HTTPException(
            status_code=503,
            detail=f"Care MCP 오류: {error}",
        ) from error

    return create_care_success_response(
        "육아 기록이 저장되었습니다.",
        data,
    )


@router.get("/care-logs")
async def get_care_logs_api(
    query: CareRecordsQuery = Depends(),
    user_id: str = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """오늘·기간·패턴·마지막 수유 기록을 Care MCP에서 조회합니다."""
    try:
        data = await get_care_logs(
            session,
            user_id,
            query,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail="Care MCP 서버 연결 또는 응답 처리에 실패했습니다.",
        ) from error

    return create_care_success_response(
        "육아 기록을 조회했습니다.",
        data,
    )


@router.get("/care-patterns/{baby_id}")
async def get_care_pattern_api(
    baby_id: str,
    days: int = Query(default=7, ge=1, le=30),
    user_id: str = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """최근 생활 패턴을 Care MCP에서 조회합니다."""
    try:
        data = await get_care_pattern(
            session,
            user_id,
            baby_id,
            days,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail="Care MCP 서버 연결 또는 응답 처리에 실패했습니다.",
        ) from error

    return create_care_success_response(
        "최근 생활 패턴을 조회했습니다.",
        data,
    )


@router.patch("/care-logs/{log_id}")
async def update_care_log_api(
    log_id: str,
    update_request: CareLogUpdateRequest,
    user_id: str = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """확인받은 육아 기록을 수정합니다."""
    try:
        data = await update_care_log(session, user_id, log_id, update_request)
    except ValueError as error:
        raise HTTPException(
            status_code=404 if "찾을 수 없습니다" in str(error) else 400,
            detail=str(error),
        ) from error
    return create_care_success_response("육아 기록을 수정했습니다.", data)


@router.delete("/care-logs/{log_id}")
async def delete_care_log_api(
    log_id: str,
    user_id: str = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """확인받은 육아 기록을 삭제합니다."""
    try:
        await delete_care_log(session, user_id, log_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return create_care_success_response("육아 기록을 삭제했습니다.", {"log_id": log_id})


@router.get("/growth/{baby_id}")
async def get_growth_api(
    baby_id: str,
    request: Request,
    user_id: str = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """성장 기록과 로컬 참고 데이터를 함께 반환합니다."""
    try:
        baby, records = await get_growth_records(session, user_id, baby_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="Care MCP 서버 연결 또는 응답 처리에 실패했습니다.") from error

    try:
        data = build_growth_information(baby, records)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return create_care_success_response(
        "성장 기록을 조회했습니다.",
        data,
    )
