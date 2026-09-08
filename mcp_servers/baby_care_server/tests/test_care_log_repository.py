"""로컬 PostgreSQL을 사용하는 Repository 통합 테스트입니다."""

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from ..repositories import care_log_repository


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1일 때만 로컬 PostgreSQL 통합 테스트를 실행합니다.",
)


@pytest.fixture
def test_ids():
    suffix = uuid4().hex
    values = {
        "baby_id": f"repo-test-baby-{suffix}",
        "feeding_id": f"repo-test-feeding-{suffix}",
        "sleep_id": f"repo-test-sleep-{suffix}",
        "feeding_key": f"repo-test-feeding-key-{suffix}",
        "sleep_key": f"repo-test-sleep-key-{suffix}",
    }
    with care_log_repository.connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO babies (
                id, user_id, baby_name, birth_date, gender, feeding_type, allergies
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (values["baby_id"], "test-user-004", "저장소 테스트 아기", "2026-08-03", "female", "formula", "[]"),
        )
    yield values
    with care_log_repository.connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM care_logs WHERE id = ANY(%s)",
            ([values["feeding_id"], values["sleep_id"]],),
        )
        cursor.execute("DELETE FROM babies WHERE id = %s", (values["baby_id"],))


def test_baby_exists() -> None:
    assert care_log_repository.baby_exists("baby-001") is True
    assert care_log_repository.baby_exists("missing-baby") is False


def test_insert_find_and_range_query(test_ids) -> None:
    recorded_at = datetime.now(timezone.utc)
    saved = care_log_repository.insert_care_log(
        log_id=test_ids["feeding_id"],
        baby_id=test_ids["baby_id"],
        event_type="feeding",
        recorded_at=recorded_at,
        details={"feeding_type": "formula", "amount_ml": 0},
        idempotency_key=test_ids["feeding_key"],
    )

    assert saved["log_id"] == test_ids["feeding_id"]
    assert saved["details"]["amount_ml"] == 0

    duplicate = care_log_repository.find_by_idempotency_key(test_ids["feeding_key"])
    assert duplicate is not None
    assert duplicate["log_id"] == test_ids["feeding_id"]

    records = care_log_repository.find_records_by_date_range(
        baby_id=test_ids["baby_id"],
        start_at=recorded_at - timedelta(minutes=1),
        end_at=recorded_at + timedelta(minutes=1),
    )
    assert any(row["log_id"] == test_ids["feeding_id"] for row in records)

    latest = care_log_repository.find_latest_feeding(test_ids["baby_id"])
    assert latest is not None
    assert latest["log_id"] == test_ids["feeding_id"]


def test_find_open_sleep(test_ids) -> None:
    care_log_repository.insert_care_log(
        log_id=test_ids["sleep_id"],
        baby_id=test_ids["baby_id"],
        event_type="sleep",
        recorded_at=datetime.now(timezone.utc),
        details={"action": "start"},
        idempotency_key=test_ids["sleep_key"],
    )

    open_sleep = care_log_repository.find_open_sleep(test_ids["baby_id"])
    assert open_sleep is not None
    assert open_sleep["log_id"] == test_ids["sleep_id"]
