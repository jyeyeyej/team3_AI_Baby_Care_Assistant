"""Care MCP를 이용한 육아 기록 업무를 처리합니다."""

from datetime import date
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp_clients.baby_care_client import (
    get_care_records as get_care_records_from_mcp,
    record_care_event,
)
from app.schemas.care import CareLogCreateRequest, CareLogUpdateRequest, CareRecordsQuery
from app.services.baby_service import get_baby


def get_mcp_data(result: dict) -> dict:
    """Care MCP 성공 응답에서 실제 data 값을 추출합니다."""
    if not result.get("success"):
        raise ValueError(result.get("message", "Care MCP 요청에 실패했습니다."))

    data = result.get("data")

    if not isinstance(data, dict):
        raise RuntimeError("Care MCP 응답 형식이 올바르지 않습니다.")

    return data


async def create_care_log(
    session: AsyncSession,
    user_id: str,
    care_request: CareLogCreateRequest,
) -> dict:
    """소유권을 확인한 뒤 육아 기록을 Care MCP에 저장합니다."""
    await get_baby(session, user_id, care_request.baby_id)

    # STT 기록은 사용자가 승인한 경우에만 Care MCP로 전달합니다.
    if care_request.input_source == "stt" and not care_request.confirmed_by_user:
        raise ValueError("STT 기록은 사용자 승인 후 저장할 수 있습니다.")

    # 모든 기록 유형에 공통으로 필요한 값입니다.
    arguments = {
        "baby_id": care_request.baby_id,
        "event_type": care_request.event_type,
        "input_source": care_request.input_source,
        "idempotency_key": care_request.idempotency_key,
    }

    if care_request.recorded_at is not None:
        arguments["recorded_at"] = care_request.recorded_at.isoformat()

    if care_request.input_source == "stt":
        arguments["confirmed_by_user"] = True

    # MCP Tool에는 현재 기록 유형에 필요한 필드만 전달합니다.
    if care_request.event_type == "feeding":
        arguments["feeding_type"] = care_request.feeding_type

        if care_request.amount_ml is not None:
            arguments["amount_ml"] = care_request.amount_ml

    if care_request.event_type == "sleep":
        arguments["action"] = care_request.action

    if care_request.event_type == "diaper":
        arguments["urine"] = care_request.urine
        arguments["stool"] = care_request.stool

        if care_request.color is not None:
            arguments["color"] = care_request.color

        if care_request.consistency is not None:
            arguments["consistency"] = care_request.consistency

        if care_request.note is not None:
            arguments["note"] = care_request.note

    if care_request.event_type == "growth":
        if care_request.weight_kg is not None:
            arguments["weight_kg"] = care_request.weight_kg

        if care_request.height_cm is not None:
            arguments["height_cm"] = care_request.height_cm

        if care_request.head_circumference_cm is not None:
            arguments["head_circumference_cm"] = care_request.head_circumference_cm

    result = await record_care_event(arguments)

    return get_mcp_data(result)


async def get_care_logs(
    session: AsyncSession,
    user_id: str,
    query: CareRecordsQuery,
) -> dict:
    """소유권을 확인한 뒤 육아 기록을 조회합니다."""
    await get_baby(session, user_id, query.baby_id)

    arguments = {
        "baby_id": query.baby_id,
        "query_type": query.query_type,
    }

    if query.start_date is not None:
        arguments["start_date"] = query.start_date.isoformat()

    if query.end_date is not None:
        arguments["end_date"] = query.end_date.isoformat()

    if query.query_type == "pattern":
        arguments["days"] = query.days

    result = await get_care_records_from_mcp(arguments)

    return get_mcp_data(result)


async def get_care_pattern(
    session: AsyncSession,
    user_id: str,
    baby_id: str,
    days: int,
) -> dict:
    """소유권을 확인한 뒤 최근 생활 패턴을 조회합니다."""
    await get_baby(session, user_id, baby_id)

    result = await get_care_records_from_mcp(
        {
            "baby_id": baby_id,
            "query_type": "pattern",
            "days": days,
        }
    )

    return get_mcp_data(result)


async def update_care_log(
    session: AsyncSession,
    user_id: str,
    log_id: str,
    update_request: CareLogUpdateRequest,
) -> dict:
    """소유한 기록만 수정한다. Care Server가 소유한 테이블을 직접 갱신한다."""
    row = (
        await session.execute(
            text(
                """
                SELECT care_logs.id AS log_id, care_logs.baby_id,
                       care_logs.log_type AS event_type, care_logs.recorded_at,
                       care_logs.details
                FROM care_logs
                JOIN babies ON babies.id = care_logs.baby_id
                WHERE care_logs.id = :log_id AND babies.user_id = :user_id
                """
            ),
            {"log_id": log_id, "user_id": user_id},
        )
    ).mappings().first()
    if row is None:
        raise ValueError("육아 기록을 찾을 수 없습니다.")

    updates = update_request.model_dump(exclude_unset=True, exclude={"recorded_at"})
    allowed_by_event = {
        "feeding": {"feeding_type", "amount_ml"},
        "sleep": {"action"},
        "diaper": {"urine", "stool", "color", "consistency", "note"},
        "growth": {"weight_kg", "height_cm", "head_circumference_cm"},
    }
    unsupported = set(updates) - allowed_by_event[row["event_type"]]
    if unsupported:
        raise ValueError("현재 기록 유형에 수정할 수 없는 값이 포함되어 있습니다.")

    details = dict(row["details"])
    details.update(updates)
    event_type = row["event_type"]
    if event_type == "feeding" and not details.get("feeding_type"):
        raise ValueError("수유 기록에는 수유 방식이 필요합니다.")
    if event_type == "sleep" and not details.get("action"):
        raise ValueError("수면 기록에는 시작 또는 종료가 필요합니다.")
    if event_type == "diaper" and not details.get("urine") and not details.get("stool"):
        raise ValueError("기저귀 기록에는 소변 또는 대변을 선택해 주세요.")
    if event_type == "growth" and not any(
        details.get(key) is not None
        for key in ("weight_kg", "height_cm", "head_circumference_cm")
    ):
        raise ValueError("성장 기록에는 수치 하나 이상이 필요합니다.")

    updated = (
        await session.execute(
            text(
                """
                UPDATE care_logs
                SET recorded_at = COALESCE(:recorded_at, recorded_at),
                    details = CAST(:details AS jsonb), updated_at = NOW()
                WHERE id = :log_id
                RETURNING id AS log_id, baby_id, log_type AS event_type,
                          recorded_at, details, updated_at
                """
            ),
            {
                "log_id": log_id,
                "recorded_at": update_request.recorded_at,
                "details": json.dumps(details),
            },
        )
    ).mappings().one()
    await session.commit()
    return dict(updated)


async def delete_care_log(
    session: AsyncSession,
    user_id: str,
    log_id: str,
) -> None:
    """로그인한 보호자가 소유한 육아 기록만 삭제한다."""
    deleted = (
        await session.execute(
            text(
                """
                DELETE FROM care_logs
                USING babies
                WHERE care_logs.id = :log_id
                  AND babies.id = care_logs.baby_id
                  AND babies.user_id = :user_id
                RETURNING care_logs.id
                """
            ),
            {"log_id": log_id, "user_id": user_id},
        )
    ).scalar_one_or_none()
    if deleted is None:
        raise ValueError("육아 기록을 찾을 수 없습니다.")
    await session.commit()


async def get_growth_records(
    session: AsyncSession,
    user_id: str,
    baby_id: str,
) -> tuple[object, list[dict]]:
    """Care Server의 전체 기간 기록 중 성장 기록만 반환한다."""
    baby = await get_baby(session, user_id, baby_id)
    result = await get_care_records_from_mcp(
        {
            "baby_id": baby_id,
            "query_type": "range",
            "start_date": baby.birth_date.isoformat(),
            "end_date": date.today().isoformat(),
        }
    )
    data = get_mcp_data(result)
    records = [
        record for record in data.get("records", [])
        if record.get("event_type") == "growth"
    ]
    return baby, records
