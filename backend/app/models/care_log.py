"""Shared care_logs model; this backend only updates/deletes owned rows."""

from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.baby import Base


class CareLog(Base):
    __tablename__ = "care_logs"
    __table_args__ = (CheckConstraint("log_type IN ('feeding', 'sleep', 'diaper', 'growth')",
                                      name="ck_care_logs_log_type"),)
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    baby_id: Mapped[str] = mapped_column(String(100), ForeignKey("babies.id", ondelete="RESTRICT"), index=True)
    log_type: Mapped[str] = mapped_column(String(20), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
