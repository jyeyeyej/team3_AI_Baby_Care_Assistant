"""예방접종 목데이터를 아기의 월령에 맞춰 조회합니다."""

from datetime import date, timedelta

from app.models.baby import Baby
from app.repositories.vaccination_repository import load_schedule


def get_vaccinations(baby: Baby) -> dict:
    """실제 접종 이력이 아닌, 시연용 권장 일정만 반환합니다."""
    schedule = load_schedule()
    age_months = max(0, (date.today() - baby.birth_date).days // 30)
    items = []
    for item in schedule:
        recommended_month = item.recommended_month
        scheduled_date = baby.birth_date + timedelta(days=recommended_month * 30)
        items.append(
            {
                "name": item.name,
                "dose": item.dose,
                "recommended_month": recommended_month,
                "scheduled_date": scheduled_date.isoformat(),
                "status": "completed_mock" if recommended_month < age_months else "upcoming",
            }
        )

    next_item = next((item for item in items if item["status"] == "upcoming"), None)
    return {
        "baby_id": baby.id,
        "age_months": age_months,
        "completed": [item for item in items if item["status"] == "completed_mock"],
        "next": next_item,
        "items": items,
        "notice": "예방접종 정보는 실제 접종 이력이 아닌 테스트용 목데이터입니다.",
    }
