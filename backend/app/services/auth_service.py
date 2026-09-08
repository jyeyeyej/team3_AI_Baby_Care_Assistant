"""테스트 사용자 로그인 처리를 담당합니다."""

import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.baby_repository import get_baby_by_user_id

BACKEND_ROOT = Path(__file__).resolve().parents[2]
TEST_USERS_FILE = BACKEND_ROOT / "data" / "test_users.json"


def load_test_users() -> list[dict]:
    """테스트 사용자 목록을 JSON 파일에서 읽습니다."""
    with TEST_USERS_FILE.open(encoding="utf-8") as file:
        return json.load(file)


def find_test_user(user_id: str) -> dict | None:
    """user_id와 일치하는 테스트 사용자를 반환합니다."""
    test_users = load_test_users()

    for user in test_users:
        if user["user_id"] == user_id:
            return user

    return None


async def get_login_baby_id(
    session: AsyncSession,
    user: dict,
) -> str | None:
    """DB에 등록된 아기를 우선 사용하고, 없으면 목데이터의 아기 ID를 사용합니다."""
    baby = await get_baby_by_user_id(session, user["user_id"])

    if baby is not None:
        return baby.id

    return user.get("baby_id")


async def get_login_session(
    redis_client,
    user_id: str,
    session_id: str,
) -> dict | None:
    """Redis에서 로그인 세션을 조회하고 사용자 일치 여부를 확인합니다."""
    session_key = f"session:{user_id}:{session_id}"
    session_json = await redis_client.get(session_key)

    if session_json is None:
        return None

    session_data = json.loads(session_json)

    if session_data.get("user_id") != user_id:
        return None

    if session_data.get("session_id") != session_id:
        return None

    return session_data
