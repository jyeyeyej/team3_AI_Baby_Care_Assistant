"""FastAPI 연결 전 화면 개발을 위한 목데이터 API 계층.

백엔드가 준비되면 각 함수의 반환부를 requests 호출로 교체한다.
페이지 파일은 이 모듈의 함수만 호출한다.
"""

from __future__ import annotations

from datetime import date


BABY = {
    "baby_id": "baby-seoa-001",
    "baby_name": "서아",
    "birth_date": "2026-08-03",
    "age_days": 31,
    "gender": "여아",
    "feeding_type": "분유",
    "current_weight_kg": 4.2,
    "birth_weight_kg": 3.2,
    "current_height_cm": 54.1,
    "head_circumference_cm": 37.0,
    "allergies": ["땅콩"],
}


def test_login(_: str) -> dict:
    return {"success": True, "data": {"user_id": "guardian-seoa", "baby_id": BABY["baby_id"], "session_id": "demo-session"}}


def get_baby(_: str) -> dict:
    return {"success": True, "data": BABY.copy()}


def get_dashboard(_: str) -> dict:
    return {
        "success": True,
        "data": {
            "feeding": {"average_count": 7, "average_interval": "평균 3시간 10분 간격"},
            "sleep": {"daily_hours": "15시간", "last": "어제 22:10"},
            "diaper": {"daily_count": 5, "detail": "소변 4회 · 대변 1회"},
            "next_vaccination": {"date": "9월 18일", "name": "DTaP 1차 · IPV 1차", "remaining": "14일 남았어요."},
        },
    }


def get_care_records(_: str) -> dict:
    return {
        "success": True,
        "data": [
            {"time": "오늘 14:30", "icon": "🍼", "title": "분유 수유", "detail": "100ml · 알림 확인으로 기록"},
            {"time": "오늘 12:05", "icon": "🌙", "title": "낮잠 종료", "detail": "10:20–12:05 · 1시간 45분"},
            {"time": "오늘 09:40", "icon": "💩", "title": "기저귀 · 대변", "detail": "노란색, 묽은 형태 · 사진 분석 메모 있음"},
            {"time": "9월 2일", "icon": "📏", "title": "성장 측정", "detail": "몸무게 4.2kg · 키 54.1cm · 머리둘레 37cm"},
        ],
    }


def get_care_pattern(_: str) -> dict:
    return {
        "success": True,
        "data": {
            "sufficient_data": True,
            "average_interval": "3시간 12분",
            "daily_feeding": "6.7회",
            "daily_sleep": "7.8시간",
            "daily_diaper": "2.7회",
            "intervals": [2.7, 3.0, 2.8, 3.4, 3.1, 3.6, 3.45],
        },
    }


def get_growth(_: str) -> dict:
    return {
        "success": True,
        "data": {
            "weight": [3.2, 3.45, 3.7, 4.0, 4.2],
            "height": [50.0, 51.2, 52.4, 53.4, 54.1],
            "head": [34.0, 34.8, 35.8, 36.5, 37.0],
            "reference": [3.45, 3.6, 3.85, 4.1, 4.35],
        },
    }


def get_vaccinations(_: str) -> dict:
    return {
        "success": True,
        "data": {
            "next": {"name": "B형간염 2차", "period": "생후 1개월 권장 일정 기준", "date": "2026. 09. 06 예정"},
            "items": [
                ("BCG", "결핵 예방 · 1회", "접종 완료 · 8/10", "done"),
                ("B형간염 1차", "출생 직후", "접종 완료 · 8/03", "done"),
                ("B형간염 2차", "생후 1개월", "접종 예정 · 9/06", "soon"),
                ("DTaP·IPV·Hib 1차", "생후 2개월", "예정 · 10/03", "future"),
            ],
        },
    }


def send_chat(message: str) -> dict:
    return {
        "success": True,
        "data": {
            "response_type": "text",
            "answer": "생후 30일 아기의 수유량은 아기마다 달라요. 서아의 최근 수유 기록과 배고픔 신호를 함께 살펴보세요. 평소와 크게 달라지거나 걱정되는 변화가 있으면 소아과에 문의해 주세요.",
            "sources": ["공식 육아정보 기반 · 수유 참고"],
        },
    }

