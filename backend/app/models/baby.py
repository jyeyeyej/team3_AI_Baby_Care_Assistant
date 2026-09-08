"""아기 정보 데이터베이스 모델을 정의합니다."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """모든 데이터베이스 모델이 공통으로 사용할 기준 클래스입니다."""


class Baby(Base):
    """babies 테이블과 연결되는 아기 정보 모델입니다."""

    __tablename__ = "babies"

    id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    baby_name: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    birth_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    gender: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    current_weight_kg: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    current_height_cm: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    feeding_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    allergies: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
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