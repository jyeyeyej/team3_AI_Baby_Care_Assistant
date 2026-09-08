"""의료기관 Tool의 입력·공공데이터 응답 변환 계약을 검증한다."""

from pathlib import Path
import sys

import pytest
from pydantic import ValidationError


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from schemas.hospital import HospitalSearchRequest
from services.hospital_service import ExternalApiError, HospitalService


def test_hospital_request_trims_region_and_enforces_bounds() -> None:
    request = HospitalSearchRequest(region="  서울특별시 동작구  ", page=1, limit=30)

    assert request.region == "서울특별시 동작구"
    with pytest.raises(ValidationError):
        HospitalSearchRequest(region=" ", page=1, limit=10)
    with pytest.raises(ValidationError):
        HospitalSearchRequest(region="서울", page=0, limit=10)
    with pytest.raises(ValidationError):
        HospitalSearchRequest(region="서울", page=1, limit=31)


def test_extract_and_normalize_pediatric_items() -> None:
    payload = {
        "response": {
            "body": {
                "items": {
                    "item": [
                        {
                            "dutyName": "예시소아청소년과",
                            "dutyAddr": "서울특별시 동작구 예시로 1",
                            "dutyTel1": "02-000-0000",
                        },
                        {"dutyName": "주소 없는 기관"},
                    ]
                }
            }
        }
    }

    items = HospitalService._normalize_items(
        "pediatric", HospitalService._extract_items(payload)
    )

    assert len(items) == 1
    assert items[0].hospital_name == "예시소아청소년과"
    assert items[0].phone == "02-000-0000"
    assert items[0].operating_hours is None


def test_provider_specific_request_parameters_and_region_filtering() -> None:
    pediatric = HospitalService._build_params(
        "pediatric", "key", "서울특별시 동작구", page=2, limit=10
    )
    emergency = HospitalService._build_params(
        "emergency", "key", "서울특별시 동작구", page=2, limit=10
    )

    assert pediatric["pageNo"] == 2
    assert pediatric["numOfRows"] == 10
    assert pediatric["sidoCd"] == "110000"
    assert pediatric["dgsbjtCd"] == "11"
    assert emergency["Q0"] == "서울특별시"
    assert emergency["Q1"] == "동작구"
    assert emergency["QZ"] == "A"
    assert emergency["ORD"] == "ADDR"

    encoded_key = HospitalService._build_params("pediatric", "abc%2Fdef%3D", "서울특별시", 1, 10)
    assert encoded_key["serviceKey"] == "abc/def="

    rows = [
        {"yadmNm": "예시소아과", "addr": "서울특별시 동작구 예시로 1"},
        {"yadmNm": "소아과 진료 병원", "addr": "서울특별시 동작구 예시로 2"},
        {"yadmNm": "다른소아과", "addr": "서울특별시 강남구 예시로 3"},
    ]
    filtered = HospitalService._filter_region("pediatric", rows, "서울특별시 동작구")
    assert filtered == rows[:2]


def test_normalize_pediatric_nhis_field_names() -> None:
    items = HospitalService._normalize_items(
        "pediatric", [{"yadmNm": "예시소아과", "addr": "서울특별시 동작구", "telno": "02-123"}]
    )
    assert items[0].hospital_name == "예시소아과"
    assert items[0].phone == "02-123"


def test_normalize_emergency_keeps_only_emergency_fields() -> None:
    items = HospitalService._normalize_items(
        "emergency",
        [{"name": "예시응급의료센터", "addr": "서울특별시 동작구 예시로 2", "level": "regional"}],
    )

    assert len(items) == 1
    assert items[0].emergency_level == "regional"
    assert not hasattr(items[0], "operating_hours")


def test_payload_business_error_is_not_treated_as_empty_result() -> None:
    with pytest.raises(ExternalApiError):
        HospitalService._raise_if_payload_error(
            {"response": {"header": {"resultCode": "30"}}}
        )
