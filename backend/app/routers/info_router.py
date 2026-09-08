"""Hospital search routes."""

from uuid import uuid4

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.info import HospitalSearchResponse
from app.services.auth_service import get_login_session
from app.services.baby_service import get_baby
from app.services.info.hospital_service import search_hospitals
from app.services.info.vaccination_service import get_vaccinations


router = APIRouter(prefix="/api", tags=["병원 검색"])


async def get_db_session(request: Request):
    async with AsyncSession(request.app.state.db_engine, expire_on_commit=False) as session:
        yield session


async def get_authenticated_user(request: Request) -> str:
    user_id = request.headers.get("X-User-Id", "")
    session_id = request.headers.get("X-Session-Id", "")
    login_session = await get_login_session(request.app.state.redis, user_id, session_id)
    if login_session is None:
        raise HTTPException(status_code=401, detail="로그인 세션이 없거나 만료되었습니다.")
    return login_session["user_id"]


@router.get("/hospitals/search")
async def search_hospitals_api(
    region: str = Query(min_length=2, max_length=100),
    type: str = Query(pattern="^(pediatric|emergency)$"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=30),
    _user_id: str = Depends(get_authenticated_user),
) -> dict:
    try:
        data = await search_hospitals(type, region.strip(), page, limit)
    except ValueError as exc:
        # Info MCP가 공공데이터 설정 누락·업무 오류를 명시적으로 반환한 경우도
        # 클라이언트가 재시도 가능한 외부 의존성 장애로 취급한다.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="병원 검색 서비스에 연결할 수 없습니다.") from exc
    return {"success": True, "message": "병원 검색 결과를 조회했습니다.", "data": HospitalSearchResponse.model_validate(data), "request_id": str(uuid4())}


@router.get("/vaccinations/{baby_id}")
async def get_vaccinations_api(
    baby_id: str,
    user_id: str = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """아기 소유권을 확인한 뒤 예방접종 목데이터를 반환합니다."""
    try:
        baby = await get_baby(session, user_id, baby_id)
        data = get_vaccinations(baby)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {
        "success": True,
        "message": "예방접종 목데이터를 조회했습니다.",
        "data": data,
        "request_id": str(uuid4()),
    }
