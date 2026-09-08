"""테스트 로그인 API를 제공합니다."""

import json
from datetime import date
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth import (
    TestLoginData,
    TestLoginRequest,
    TestLoginResponse,
)
from app.models.baby import Baby
from app.repositories.baby_repository import get_baby_by_user_id
from app.services.auth_service import find_test_user


router = APIRouter(prefix="/api", tags=["인증"])


@router.post("/test-login", response_model=TestLoginResponse)
async def test_login(
    login_request: TestLoginRequest,
    request: Request,
) -> TestLoginResponse:
    """선택한 테스트 사용자로 로그인하고 Redis 세션을 생성합니다."""
    user = find_test_user(login_request.user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="테스트 사용자를 찾을 수 없습니다.",
        )

    async with AsyncSession(
        request.app.state.db_engine,
        expire_on_commit=False,
    ) as session:
        baby = await get_baby_by_user_id(session, user["user_id"])
        if baby is None and user.get("baby_id"):
            # Test login remains passwordless, but provisions its demo baby so
            # authenticated chat can use the same real DB and MCP workflow.
            is_seoa = user["user_id"] == "user-001"
            baby = Baby(
                id=user["baby_id"],
                user_id=user["user_id"],
                baby_name="서아" if is_seoa else "민준",
                birth_date=date(2026, 8, 3) if is_seoa else date(2026, 3, 10),
                gender="여아" if is_seoa else "남아",
                current_weight_kg=4.2 if is_seoa else 7.4,
                current_height_cm=54.1 if is_seoa else 67.0,
                feeding_type="formula" if is_seoa else "mixed",
                allergies=["땅콩"] if is_seoa else [],
            )
            session.add(baby)
            await session.commit()
        baby_id = baby.id if baby is not None else None

    session_id = str(uuid4())
    request_id = str(uuid4())

    session_data = {
        "user_id": user["user_id"],
        "baby_id": baby_id,
        "session_id": session_id,
        "request_id": request_id,
        "status": "waiting",
    }

    session_key = f"session:{user['user_id']}:{session_id}"

    await request.app.state.redis.set(
        session_key,
        json.dumps(session_data, ensure_ascii=False),
        ex=86400,
    )

    return TestLoginResponse(
        message="테스트 사용자로 로그인했습니다.",
        data=TestLoginData(
            user_id=user["user_id"],
            guardian_name=user["guardian_name"],
            baby_id=baby_id,
            session_id=session_id,
        ),
        request_id=request_id,
    )
