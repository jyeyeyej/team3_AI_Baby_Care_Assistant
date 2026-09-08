"""수유 record_care_event의 PostgreSQL 통합 테스트입니다."""

import os
from uuid import uuid4

import pytest

from ..repositories import care_log_repository
from ..schemas.care import RecordCareEventInput
from ..services.care_service import record_care_event


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1일 때만 로컬 PostgreSQL 통합 테스트를 실행합니다.",
)


@pytest.fixture
def baby_id():
    value = f"record-test-baby-{uuid4().hex}"
    with care_log_repository.connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO babies (
                id, user_id, baby_name, birth_date, gender, feeding_type, allergies
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (value, "test-user-001", "기록 테스트 아기", "2026-08-03", "female", "formula", "[]"),
        )
    yield value
    with care_log_repository.connect() as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM care_logs WHERE baby_id = %s", (value,))
        cursor.execute("DELETE FROM babies WHERE id = %s", (value,))


def make_request(baby_id: str, **changes) -> RecordCareEventInput:
    data = {
        "baby_id": baby_id,
        "event_type": "feeding",
        "input_source": "ui",
        "idempotency_key": f"record-test-key-{uuid4().hex}",
        "feeding_type": "formula",
        "amount_ml": 0,
    }
    data.update(changes)
    return RecordCareEventInput(**data)


@pytest.mark.parametrize("input_source", ["text", "ui"])
def test_text_and_ui_save_without_confirmation(baby_id: str, input_source: str) -> None:
    response = record_care_event(
        make_request(baby_id, input_source=input_source, confirmed_by_user=False)
    )
    assert response.success is True
    assert response.data is not None
    assert response.data.duplicated is False


def test_stt_without_confirmation_is_rejected(baby_id: str) -> None:
    response = record_care_event(
        make_request(baby_id, input_source="stt", confirmed_by_user=False)
    )
    assert response.success is False
    assert response.error is not None
    assert response.error.code == "STT_CONFIRMATION_REQUIRED"


def test_confirmed_stt_is_saved(baby_id: str) -> None:
    response = record_care_event(
        make_request(baby_id, input_source="stt", confirmed_by_user=True)
    )
    assert response.success is True


def test_missing_baby_is_rejected() -> None:
    response = record_care_event(make_request("missing-baby"))
    assert response.success is False
    assert response.error is not None
    assert response.error.code == "BABY_NOT_FOUND"


def test_duplicate_key_returns_existing_result(baby_id: str) -> None:
    key = f"record-test-key-{uuid4().hex}"
    request = make_request(baby_id, idempotency_key=key, amount_ml=100)

    first = record_care_event(request)
    second = record_care_event(request)

    assert first.success is True
    assert second.success is True
    assert first.data is not None
    assert second.data is not None
    assert first.data.log_id == second.data.log_id
    assert first.data.duplicated is False
    assert second.data.duplicated is True


def test_duplicate_key_for_another_baby_is_rejected(baby_id: str) -> None:
    other_baby_id = f"record-test-baby-{uuid4().hex}"
    key = f"record-test-key-{uuid4().hex}"
    with care_log_repository.connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO babies (
                id, user_id, baby_name, birth_date, gender, feeding_type, allergies
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (other_baby_id, "test-user-002", "중복 테스트 아기", "2026-08-03", "female", "formula", "[]"),
        )

    try:
        first = record_care_event(make_request(baby_id, idempotency_key=key))
        conflict = record_care_event(make_request(other_baby_id, idempotency_key=key))

        assert first.success is True
        assert conflict.success is False
        assert conflict.error is not None
        assert conflict.error.code == "IDEMPOTENCY_KEY_CONFLICT"
    finally:
        with care_log_repository.connect() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM care_logs WHERE baby_id = %s", (other_baby_id,))
            cursor.execute("DELETE FROM babies WHERE id = %s", (other_baby_id,))


def test_feeding_type_is_required(baby_id: str) -> None:
    response = record_care_event(make_request(baby_id, feeding_type=None))
    assert response.success is False
    assert response.error is not None
    assert response.error.code == "INVALID_CARE_EVENT"


@pytest.mark.parametrize(
    ("urine", "stool"),
    [(True, False), (False, True), (True, True)],
)
def test_valid_diaper_record_is_saved(
    baby_id: str, urine: bool, stool: bool
) -> None:
    key = f"record-test-key-{uuid4().hex}"
    response = record_care_event(
        make_request(
            baby_id,
            event_type="diaper",
            idempotency_key=key,
            feeding_type=None,
            amount_ml=None,
            urine=urine,
            stool=stool,
            color="yellow",
            consistency="soft",
            memo="테스트 메모",
        )
    )

    assert response.success is True
    assert response.data is not None
    saved = care_log_repository.find_by_idempotency_key(key)
    assert saved is not None
    assert response.data.event_type == "diaper"
    assert saved["details"]["urine"] is urine
    assert saved["details"]["stool"] is stool


@pytest.mark.parametrize(
    ("urine", "stool"),
    [(False, False), (None, None), (False, None), (None, False)],
)
def test_diaper_requires_urine_or_stool(
    baby_id: str, urine: bool | None, stool: bool | None
) -> None:
    response = record_care_event(
        make_request(
            baby_id,
            event_type="diaper",
            feeding_type=None,
            amount_ml=None,
            urine=urine,
            stool=stool,
        )
    )

    assert response.success is False
    assert response.error is not None
    assert response.error.code == "INVALID_CARE_EVENT"


def test_diaper_stores_only_diaper_details(baby_id: str) -> None:
    key = f"record-test-key-{uuid4().hex}"
    response = record_care_event(
        make_request(
            baby_id,
            event_type="diaper",
            idempotency_key=key,
            urine=True,
            stool=False,
            color="yellow",
            consistency=None,
            memo="정상 기록",
            feeding_type="formula",
            amount_ml=120,
        )
    )

    assert response.success is True
    saved = care_log_repository.find_by_idempotency_key(key)
    assert saved is not None
    assert saved["details"] == {
        "urine": True,
        "stool": False,
        "color": "yellow",
        "memo": "정상 기록",
    }


@pytest.mark.parametrize(
    "growth_values",
    [
        {"weight_kg": 7.2},
        {"height_cm": 66.0},
        {"head_circumference_cm": 42.0},
        {
            "weight_kg": 7.2,
            "height_cm": 66.0,
            "head_circumference_cm": 42.0,
        },
    ],
)
def test_growth_with_at_least_one_value_is_saved(
    baby_id: str, growth_values: dict[str, float]
) -> None:
    key = f"record-test-key-{uuid4().hex}"
    response = record_care_event(
        make_request(
            baby_id,
            event_type="growth",
            idempotency_key=key,
            feeding_type=None,
            amount_ml=None,
            **growth_values,
        )
    )

    assert response.success is True
    assert response.data is not None
    assert response.data.event_type == "growth"
    saved = care_log_repository.find_by_idempotency_key(key)
    assert saved is not None
    assert saved["details"] == growth_values


def test_growth_requires_at_least_one_value(baby_id: str) -> None:
    response = record_care_event(
        make_request(
            baby_id,
            event_type="growth",
            feeding_type=None,
            amount_ml=None,
        )
    )

    assert response.success is False
    assert response.error is not None
    assert response.error.code == "INVALID_CARE_EVENT"


def test_growth_stores_only_growth_details(baby_id: str) -> None:
    key = f"record-test-key-{uuid4().hex}"
    response = record_care_event(
        make_request(
            baby_id,
            event_type="growth",
            idempotency_key=key,
            weight_kg=7.2,
            feeding_type="formula",
            amount_ml=120,
            urine=True,
            memo="저장되면 안 되는 메모",
        )
    )

    assert response.success is True
    saved = care_log_repository.find_by_idempotency_key(key)
    assert saved is not None
    assert saved["details"] == {"weight_kg": 7.2}


def make_sleep_request(
    baby_id: str, action: str | None, **changes
) -> RecordCareEventInput:
    data = {
        "event_type": "sleep",
        "feeding_type": None,
        "amount_ml": None,
        "action": action,
    }
    data.update(changes)
    return make_request(baby_id, **data)


def test_sleep_start_and_end_are_saved_in_order(baby_id: str) -> None:
    start_key = f"record-test-key-{uuid4().hex}"
    end_key = f"record-test-key-{uuid4().hex}"

    started = record_care_event(
        make_sleep_request(baby_id, "start", idempotency_key=start_key)
    )
    ended = record_care_event(
        make_sleep_request(baby_id, "end", idempotency_key=end_key)
    )

    assert started.success is True
    assert ended.success is True
    saved_start = care_log_repository.find_by_idempotency_key(start_key)
    saved_end = care_log_repository.find_by_idempotency_key(end_key)
    assert saved_start is not None
    assert saved_end is not None
    assert saved_start["details"] == {"action": "start"}
    assert saved_end["details"] == {"action": "end"}
    assert care_log_repository.find_open_sleep(baby_id) is None


def test_sleep_rejects_duplicate_start(baby_id: str) -> None:
    first = record_care_event(make_sleep_request(baby_id, "start"))
    duplicate_start = record_care_event(make_sleep_request(baby_id, "start"))

    assert first.success is True
    assert duplicate_start.success is False
    assert duplicate_start.error is not None
    assert duplicate_start.error.code == "SLEEP_ALREADY_STARTED"


def test_sleep_rejects_end_without_start(baby_id: str) -> None:
    response = record_care_event(make_sleep_request(baby_id, "end"))

    assert response.success is False
    assert response.error is not None
    assert response.error.code == "SLEEP_START_NOT_FOUND"


def test_sleep_requires_action(baby_id: str) -> None:
    response = record_care_event(make_sleep_request(baby_id, None))

    assert response.success is False
    assert response.error is not None
    assert response.error.code == "INVALID_CARE_EVENT"


def test_sleep_stores_only_action(baby_id: str) -> None:
    key = f"record-test-key-{uuid4().hex}"
    response = record_care_event(
        make_sleep_request(
            baby_id,
            "start",
            idempotency_key=key,
            feeding_type="formula",
            amount_ml=120,
            urine=True,
            weight_kg=7.2,
            memo="저장되면 안 되는 메모",
        )
    )

    assert response.success is True
    saved = care_log_repository.find_by_idempotency_key(key)
    assert saved is not None
    assert saved["details"] == {"action": "start"}
