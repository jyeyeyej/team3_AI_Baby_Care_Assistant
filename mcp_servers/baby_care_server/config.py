"""환경변수에서 baby_care_server 설정을 읽습니다."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # The Care MCP can be launched from the project root or mcp_servers;
        # always use the shared project settings rather than the working dir.
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_dsn: str = "postgresql://postgres:password@localhost:5432/baby_ai"

    openai_api_key: str = ""
    openai_vision_model: str = ""
    openai_response_model: str = ""

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_timeout_seconds: int = Field(default=30, ge=1)
    ollama_embedding_dimension: int = Field(default=768, ge=1)
    rag_top_k: int = Field(default=5, ge=1, le=10)
    rag_min_similarity: float = Field(default=0.70, ge=0, le=1)

    image_max_bytes: int = Field(default=10_485_760, ge=1)
    # FastAPI and this MCP process must resolve the same shared temp directory,
    # regardless of each process' working directory.
    image_temp_directory: Path = Path(__file__).resolve().parents[2] / "uploads"
    image_min_width: int = Field(default=224, ge=1)
    image_min_height: int = Field(default=224, ge=1)
    image_dark_threshold: float = Field(default=35.0, ge=0, le=255)
    image_bright_threshold: float = Field(default=235.0, ge=0, le=255)
    image_blur_threshold: float = Field(default=20.0, ge=0)
    app_timezone: str = "Asia/Seoul"

    mcp_host: str = "127.0.0.1"
    mcp_port: int = Field(default=8101, ge=1, le=65_535)
    mcp_streamable_http_path: str = "/mcp"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
