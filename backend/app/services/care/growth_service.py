"""Combines Care-MCP growth records with non-diagnostic local references."""

import json
from datetime import date
from pathlib import Path
from typing import Any

from app.models.baby import Baby

REFERENCE_PATH = Path(__file__).resolve().parents[3] / "data" / "growth_reference.json"


def build_growth_information(baby: Baby, records: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        reference_data = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("성장 참고 데이터를 읽을 수 없습니다.") from exc
    if not isinstance(reference_data, dict):
        raise RuntimeError("성장 참고 데이터 형식이 올바르지 않습니다.")
    age_months = max(0, min(36, (date.today() - baby.birth_date).days // 30))
    return {
        "baby_id": baby.id,
        "age_months": age_months,
        "records": records,
        "reference": reference_data.get(baby.gender, {}).get(str(age_months)),
        "reference_notice": "참고값은 진단이나 정상·비정상 판정에 사용하지 않습니다.",
    }
