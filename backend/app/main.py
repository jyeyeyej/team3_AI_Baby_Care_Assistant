"""FastAPI 애플리케이션 진입점."""

from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import POSTGRES_DSN, REDIS_URL

from app.routers.auth_router import router as auth_router

from app.models.baby import Base
from app.routers.baby_router import router as baby_router

# 서버 시작 시 PostgreSQL·Redis 연결 생성, 종료 시 연결 정리
@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 공용 연결을 만들고, 종료 시 정리합니다."""
    app.state.db_engine = create_async_engine(
        POSTGRES_DSN,
        pool_pre_ping=True,
    )
    
    app.state.redis = redis.from_url(
        REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    
    # 작성된 모델을 기준으로 없는 테이블을 개발용 DB에 생성
    async with app.state.db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield

    await app.state.redis.aclose()
    await app.state.db_engine.dispose()

# FastAPI 애플리케이션 생성 및 lifespan 등록
app = FastAPI(
    title="AI Baby Care Assistant API",
    version="0.1.0",
    lifespan=lifespan,
    
)

#라우터 등록하기
app.include_router(auth_router)
app.include_router(baby_router)

# PostgreSQL과 Redis의 연결 상태를 확인하는 헬스체크 API
@app.get("/health", tags=["시스템"])
async def health_check() -> dict:
    """PostgreSQL과 Redis 연결 상태를 확인합니다."""
    postgres_status = "ok"
    redis_status = "ok"

    # PostgreSQL에 SELECT 1을 실행해 연결 상태 확인
    try:
        db_engine: AsyncEngine = app.state.db_engine
        async with db_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        postgres_status = "error"

    # Redis에 PING을 보내 연결 상태 확인
    try:
        await app.state.redis.ping()
    except Exception:
        redis_status = "error"

    # PostgreSQL·Redis 상태를 하나의 응답으로 구성
    response = {
        "status": "ok" if postgres_status == "ok" and redis_status == "ok" else "error",
        "services": {
            "postgres": postgres_status,
            "redis": redis_status,
        },
    }

    # 하나라도 연결 실패 시 503 에러 반환
    if response["status"] == "error":
        raise HTTPException(status_code=503, detail=response)

    return response