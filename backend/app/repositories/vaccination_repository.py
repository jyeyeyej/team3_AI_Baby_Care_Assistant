"""Loads the local, demo-only vaccination schedule."""

import json
from pathlib import Path
from app.models.vaccination import VaccinationScheduleItem

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "vaccinations.json"


def load_schedule() -> list[VaccinationScheduleItem]:
    try:
        raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("예방접종 목데이터를 읽을 수 없습니다.") from exc
    if not isinstance(raw, list):
        raise RuntimeError("예방접종 목데이터 형식이 올바르지 않습니다.")
    return [VaccinationScheduleItem.model_validate(item) for item in raw]
