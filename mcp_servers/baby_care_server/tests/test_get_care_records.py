"""get_care_records의 오늘·기간 PostgreSQL 통합 테스트입니다."""

import os
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from ..repositories import care_log_repository
from ..schemas.care import GetCareRecordsInput
from ..services.care_query_service import get_care_records


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1일 때만 로컬 PostgreSQL 통합 테스트를 실행합니다.",
)

KST = ZoneInfo("Asia/Seoul")


@pytest.fixture
def query_baby_id():
    value = f"query-test-baby-{uuid4().hex}"
    with care_log_repository.connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO babies (
                id, user_id, baby_name, birth_date, gender, feeding_type, allergies
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (value, "test-user-003", "조회 테스트 아기", "2026-08-03", "female", "formula", "[]"),
        )
    yield value
    with care_log_repository.connect() as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM care_logs WHERE baby_id = %s", (value,))
        cursor.execute("DELETE FROM babies WHERE id = %s", (value,))


def insert_record(
    baby_id: str,
    recorded_at: datetime,
    event_type: str = "feeding",
    details: dict | None = None,
):
    return care_log_repository.insert_care_log(
        log_id=str(uuid4()),
        baby_id=baby_id,
        event_type=event_type,
        recorded_at=recorded_at,
        details=details or {"feeding_type": "formula", "amount_ml": 100},
        idempotency_key=f"query-test-key-{uuid4().hex}",
    )


def test_today_returns_only_korean_calendar_day(query_baby_id: str) -> None:
    today = datetime.now(KST).date()
    yesterday = today - timedelta(days=1)
    insert_record(query_baby_id, datetime.combine(yesterday, datetime.min.time(), KST))
    expected = insert_record(
        query_baby_id,
        datetime.combine(today, datetime.min.time(), KST) + timedelta(hours=12),
    )
    response = get_care_records(
        GetCareRecordsInput(baby_id=query_baby_id, query_type="today")
    )

    assert response.success is True
    assert response.data is not None
    assert [record.log_id for record in response.data.records] == [expected["log_id"]]
    assert response.data.pattern is None
    assert response.data.latest_feeding is None


def test_range_includes_both_dates_and_orders_oldest_first(
    query_baby_id: str,
) -> None:
    start_date = datetime(2026, 9, 1, tzinfo=KST).date()
    end_date = datetime(2026, 9, 3, tzinfo=KST).date()
    before = datetime(2026, 8, 31, 23, 59, tzinfo=KST)
    first = datetime(2026, 9, 1, 0, 0, tzinfo=KST)
    last = datetime(2026, 9, 3, 23, 59, tzinfo=KST)
    after = datetime(2026, 9, 4, 0, 0, tzinfo=KST)

    insert_record(query_baby_id, before)
    last_row = insert_record(query_baby_id, last, "diaper")
    first_row = insert_record(query_baby_id, first)
    insert_record(query_baby_id, after)

    response = get_care_records(
        GetCareRecordsInput(
            baby_id=query_baby_id,
            query_type="range",
            start_date=start_date,
            end_date=end_date,
        )
    )

    assert response.success is True
    assert response.data is not None
    assert [record.log_id for record in response.data.records] == [
        first_row["log_id"],
        last_row["log_id"],
    ]


def test_range_with_no_records_returns_empty_list(query_baby_id: str) -> None:
    response = get_care_records(
        GetCareRecordsInput(
            baby_id=query_baby_id,
            query_type="range",
            start_date="2026-01-01",
            end_date="2026-01-02",
        )
    )

    assert response.success is True
    assert response.data is not None
    assert response.data.records == []


def test_query_rejects_missing_baby() -> None:
    response = get_care_records(
        GetCareRecordsInput(baby_id="missing-query-baby", query_type="today")
    )

    assert response.success is False
    assert response.error is not None
    assert response.error.code == "BABY_NOT_FOUND"


def test_latest_feeding_returns_most_recent_feeding_only(
    query_baby_id: str,
) -> None:
    insert_record(query_baby_id, datetime(2026, 9, 1, 8, 0, tzinfo=KST))
    expected = insert_record(
        query_baby_id, datetime(2026, 9, 2, 8, 0, tzinfo=KST)
    )
    insert_record(
        query_baby_id,
        datetime(2026, 9, 3, 8, 0, tzinfo=KST),
        event_type="diaper",
    )

    response = get_care_records(
        GetCareRecordsInput(
            baby_id=query_baby_id,
            query_type="latest_feeding",
        )
    )

    assert response.success is True
    assert response.data is not None
    assert response.data.records == []
    assert response.data.pattern is None
    assert response.data.latest_feeding is not None
    assert response.data.latest_feeding.log_id == expected["log_id"]
    assert response.data.latest_feeding.event_type == "feeding"


def test_latest_feeding_without_feeding_returns_null(query_baby_id: str) -> None:
    insert_record(
        query_baby_id,
        datetime(2026, 9, 3, 8, 0, tzinfo=KST),
        event_type="diaper",
    )

    response = get_care_records(
        GetCareRecordsInput(
            baby_id=query_baby_id,
            query_type="latest_feeding",
        )
    )

    assert response.success is True
    assert response.data is not None
    assert response.data.records == []
    assert response.data.latest_feeding is None


def test_pattern_calculates_statistics_and_sufficient_data(
    query_baby_id: str,
) -> None:
    today = datetime.now(KST).date()
    day1 = today - timedelta(days=2)
    day2 = today - timedelta(days=1)

    insert_record(
        query_baby_id,
        datetime.combine(day1, datetime.min.time(), KST) + timedelta(hours=8),
        details={"feeding_type": "formula", "amount_ml": 0},
    )
    insert_record(
        query_baby_id,
        datetime.combine(day1, datetime.min.time(), KST) + timedelta(hours=11),
        details={"feeding_type": "formula", "amount_ml": 120},
    )
    insert_record(
        query_baby_id,
        datetime.combine(day2, datetime.min.time(), KST) + timedelta(hours=1),
        event_type="sleep",
        details={"action": "start"},
    )
    insert_record(
        query_baby_id,
        datetime.combine(day2, datetime.min.time(), KST) + timedelta(hours=3),
        event_type="sleep",
        details={"action": "end"},
    )
    insert_record(
        query_baby_id,
        datetime.combine(today, datetime.min.time(), KST) + timedelta(hours=9),
        event_type="diaper",
        details={"urine": True, "stool": True},
    )

    response = get_care_records(
        GetCareRecordsInput(baby_id=query_baby_id, query_type="pattern", days=7)
    )

    assert response.success is True
    assert response.data is not None
    assert response.data.records == []
    assert response.data.latest_feeding is None
    pattern = response.data.pattern
    assert pattern is not None
    assert pattern.record_count == 5
    assert pattern.recorded_day_count == 3
    assert pattern.sufficient_data is True
    assert pattern.insufficient_reason is None
    assert pattern.feeding.count == 2
    assert pattern.feeding.average_amount_ml == 60.0
    assert pattern.feeding.average_interval_minutes == 180.0
    assert pattern.sleep.completed_session_count == 1
    assert pattern.sleep.total_sleep_minutes == 120
    assert pattern.sleep.average_sleep_minutes == 120.0
    assert pattern.diaper.urine_count == 1
    assert pattern.diaper.stool_count == 1


def test_pattern_returns_partial_values_when_data_is_insufficient(
    query_baby_id: str,
) -> None:
    today = datetime.now(KST).date()
    insert_record(
        query_baby_id,
        datetime.combine(today, datetime.min.time(), KST) + timedelta(hours=8),
        details={"feeding_type": "breast", "amount_ml": None},
    )
    insert_record(
        query_baby_id,
        datetime.combine(today, datetime.min.time(), KST) + timedelta(hours=9),
        event_type="sleep",
        details={"action": "start"},
    )

    response = get_care_records(
        GetCareRecordsInput(baby_id=query_baby_id, query_type="pattern", days=7)
    )

    assert response.success is True
    assert response.data is not None
    pattern = response.data.pattern
    assert pattern is not None
    assert pattern.sufficient_data is False
    assert pattern.insufficient_reason is not None
    assert pattern.feeding.count == 1
    assert pattern.feeding.average_amount_ml is None
    assert pattern.feeding.average_interval_minutes is None
    assert pattern.sleep.completed_session_count == 0
    assert pattern.sleep.total_sleep_minutes is None
    assert pattern.sleep.average_sleep_minutes is None


def test_pattern_excludes_records_before_requested_period(
    query_baby_id: str,
) -> None:
    today = datetime.now(KST).date()
    insert_record(
        query_baby_id,
        datetime.combine(today - timedelta(days=7), datetime.min.time(), KST),
    )
    insert_record(
        query_baby_id,
        datetime.combine(today - timedelta(days=6), datetime.min.time(), KST),
    )

    response = get_care_records(
        GetCareRecordsInput(baby_id=query_baby_id, query_type="pattern", days=7)
    )

    assert response.data is not None
    assert response.data.pattern is not None
    assert response.data.pattern.record_count == 1
