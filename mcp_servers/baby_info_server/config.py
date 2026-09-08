import asyncio
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# psycopg 비동기 연결은 Windows 기본 Proactor 이벤트 루프와 호환되지 않는다.
# MCP 서버뿐 아니라 단독 색인·검색 실행에서도 동일하게 적용한다.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        extra="ignore",
    )

    app_env: str = "development"
    app_timezone: str = "Asia/Seoul"

    public_data_api_key: str = ""
    public_data_base_url: str = ""
    pediatric_api_key: str = ""
    pediatric_api_url: str = ""
    emergency_api_key: str = ""
    emergency_api_url: str = ""
    external_api_timeout_seconds: float = Field(default=5, gt=0)
    external_api_retry_count: int = Field(default=1, ge=0, le=3)
    openai_api_key: str = ""
    openai_response_model: str = "gpt-4.1-mini"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_timeout_seconds: float = Field(default=30, gt=0)
    embedding_dimensions: int = Field(
        default=768,
        gt=0,
        validation_alias=AliasChoices(
            "OLLAMA_EMBEDDING_DIMENSION",
            "EMBEDDING_DIMENSIONS",
        ),
    )

    postgres_dsn: str = "postgresql://postgres:password@localhost:5432/baby_ai"
    redis_url: str = "redis://127.0.0.1:6379/0"
    cache_ttl_seconds: int = Field(default=600, ge=0)

    rag_top_k: int = Field(default=5, ge=1, le=10)
    rag_min_similarity: float = Field(default=0.70, ge=0, le=1)
    rag_max_context_chars: int = Field(default=8000, ge=1000)

    mcp_host: str = "127.0.0.1"
    mcp_port: int = Field(default=8102, ge=1, le=65535)
    mcp_streamable_http_path: str = "/mcp"

    @field_validator("mcp_streamable_http_path")
    @classmethod
    def path_starts_with_slash(cls, value: str) -> str:
        return value if value.startswith("/") else f"/{value}"

    @field_validator("postgres_dsn")
    @classmethod
    def normalize_psycopg_dsn(cls, value: str) -> str:
        return value.replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_hospital_service():
    from services.hospital_service import HospitalService

    settings = get_settings()
    return HospitalService(
        base_url=settings.public_data_base_url,
        api_key=settings.public_data_api_key,
        timezone=settings.app_timezone,
        timeout_seconds=settings.external_api_timeout_seconds,
        retry_count=settings.external_api_retry_count,
        pediatric_api_url=settings.pediatric_api_url,
        pediatric_api_key=settings.pediatric_api_key,
        emergency_api_url=settings.emergency_api_url,
        emergency_api_key=settings.emergency_api_key,
    )


@lru_cache
def get_rag_service():
    from repositories.rag_repository import RagRepository
    from services.answer_service import AnswerService
    from services.embedding_service import EmbeddingService
    from services.rag_service import RagService

    settings = get_settings()
    return RagService(
        EmbeddingService(
            settings.ollama_base_url,
            settings.ollama_embedding_model,
            settings.ollama_timeout_seconds,
            settings.embedding_dimensions,
        ),
        RagRepository(settings.postgres_dsn),
        AnswerService(settings.openai_api_key, settings.openai_response_model),
        settings.rag_min_similarity,
        settings.rag_max_context_chars,
    )
