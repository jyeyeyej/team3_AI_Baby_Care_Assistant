"""Internal memory schemas; care records are deliberately excluded."""

from datetime import datetime
from pydantic import Field
from app.schemas.common import StrictBaseModel


class MemoryResponse(StrictBaseModel):
    id: str
    memory_type: str
    content: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
