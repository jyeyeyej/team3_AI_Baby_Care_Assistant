"""테스트 로그인 요청과 응답 형식을 정의합니다."""

from pydantic import BaseModel, Field


class TestLoginRequest(BaseModel):
    """테스트 로그인 요청 데이터입니다."""

    user_id: str = Field(
        min_length=1,
        max_length=100,
        description="선택한 테스트 사용자 ID",
    )


class TestLoginData(BaseModel):
    """로그인 성공 시 프론트엔드에 전달할 데이터입니다."""

    user_id: str
    guardian_name: str
    baby_id: str | None
    session_id: str


class TestLoginResponse(BaseModel):
    """테스트 로그인 API의 공통 성공 응답입니다."""

    success: bool = True
    message: str
    data: TestLoginData
    request_id: str