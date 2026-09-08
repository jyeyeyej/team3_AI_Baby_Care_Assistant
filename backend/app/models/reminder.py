"""수유 알림 설정 데이터베이스 모델을 정의합니다."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.baby import Base


class ReminderSetting(Base):
    """reminder_settings 테이블과 연결되는 수유 알림 설정 모델입니다."""

    __tablename__ = "reminder_settings"
    __table_args__ = (
        CheckConstraint(
            "feeding_interval_minutes BETWEEN 30 AND 720",
            name="ck_reminder_settings_feeding_interval",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )
    baby_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("babies.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
        index=True,
    )
    feeding_interval_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=180,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
