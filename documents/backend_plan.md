# AI 육아 도우미 백엔드 기술 개발계획서

> Python·FastAPI 기반 백엔드와 MCP 서버를 구현하기 위한 기술 명세서입니다. Streamlit 화면 구현 내용은 포함하지 않습니다.
>
> **문자열·상수 목록·Pydantic `Field(pattern=...)`**으로 약속된 값을 관리합니다.
>
> 기준: `baby_care_server_plan.md`는 고정하고 Backend가 해당 Tool/Schema 계약을 따릅니다.

---

# 0. 백엔드·MCP 서버 공통 계약

코딩 전에 FastAPI 담당자, DB 담당자, `baby_care_server` 담당자, `baby_info_server` 담당자가 아래 값을 공용 계약으로 사용합니다.

## 0.1 DB 계약 — `care_logs`

`care_logs`는 `baby_care_server`와 FastAPI가 함께 사용하는 공용 테이블입니다. ID 계열 DB 타입은 `VARCHAR(100)`으로 통일하고 `babies.id`와 `care_logs.baby_id`는 반드시 같은 자료형을 사용합니다.

```sql
CREATE TABLE care_logs (
    id VARCHAR(100) PRIMARY KEY,
    baby_id VARCHAR(100) NOT NULL,
    log_type VARCHAR(20) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_care_logs_log_type
        CHECK (log_type IN ('feeding', 'sleep', 'diaper', 'growth')),

    CONSTRAINT fk_care_logs_baby
        FOREIGN KEY (baby_id)
        REFERENCES babies(id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_care_logs_baby_recorded_at
    ON care_logs (baby_id, recorded_at DESC);

CREATE INDEX idx_care_logs_baby_log_type
    ON care_logs (baby_id, log_type);
```

공통 규칙:

- `idempotency_key`는 `UNIQUE` 제약으로 DB에서도 중복 저장을 방지합니다.
- `log_type`은 `feeding`, `sleep`, `diaper`, `growth`만 허용합니다.
- 시간은 `TIMESTAMPTZ`로 저장합니다.
- 세부 필드는 `details JSONB`에 저장합니다.
- `baby_id`는 `babies.id`를 참조하며 `ON DELETE RESTRICT`를 사용합니다.

## 0.2 MCP 요청·응답 계약

MCP Tool의 응답을 FastAPI의 공통 HTTP 응답 모양으로 강제하지 않습니다. 각 MCP 서버의 **Tool별 입력·출력 Schema가 실제 계약**이며 FastAPI의 MCP Client는 해당 계약을 그대로 받아 검증합니다.

### `baby_care_server` 공통 성공 응답

```json
{
  "success": true,
  "message": "요청을 처리했습니다.",
  "data": {},
  "error": null
}
```

### `baby_care_server` 업무 실패 응답

```json
{
  "success": false,
  "message": "요청을 처리하지 못했습니다.",
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "detail": "오류에 대한 설명"
  }
}
```

### `baby_info_server` 의료기관 Tool 성공 응답

```json
{
  "success": true,
  "region": "서울특별시 동작구",
  "data": [],
  "source": "public_data",
  "checked_at": "2026-09-03T14:00:00+09:00",
  "notice": "운영시간과 진료 가능 여부는 방문 전 의료기관에 확인해 주세요."
}
```

### `baby_info_server` 육아 지식 RAG Tool 성공 응답

```json
{
  "success": true,
  "answer": "검색 근거를 바탕으로 생성한 답변",
  "category": "feeding",
  "sources": [],
  "confidence": "high",
  "safety_notice": null
}
```

### `baby_info_server` 업무 실패 응답

```json
{
  "success": false,
  "message": "공공데이터 API를 호출할 수 없습니다.",
  "error_code": "EXTERNAL_API_ERROR"
}
```

FastAPI MCP Client 처리 원칙:

```text
baby_care_server
→ success=true: Tool별 Care 성공 Response Schema 검증
→ success=false: CareToolErrorResponse 검증

baby_info_server
→ success=true: Tool별 Info 성공 Response Schema 검증
→ success=false: InfoToolErrorResponse 검증

어느 Schema에도 맞지 않음
→ INVALID_MCP_RESPONSE
```

공통 원칙:

- `baby_care_server`의 중복 `idempotency_key`는 오류가 아니라 기존 성공 결과와 `duplicated=true`로 반환합니다.
- MCP 프로세스 중단, DB 연결 자체 실패처럼 정상 흐름으로 복구하기 어려운 서버 장애는 예외로 처리합니다.
- FastAPI는 MCP 결과를 검증한 뒤 Frontend용 공통 HTTP 응답으로 변환합니다.

## 0.3 기저귀 이미지 전달 계약

FastAPI는 **임시 이미지 경로 `image_path`**를 `analyze_infant_stool`에 전달합니다.

```text
Frontend
→ multipart/form-data 이미지 업로드
→ FastAPI 이미지 형식·크기 검증
→ 공용 임시 폴더 저장
→ baby_care_client.py
→ analyze_infant_stool(image_path, ...)
→ baby_care_server
→ 분석 완료 후 임시 이미지 삭제
```

이미지 공통 규칙:

- FastAPI 업로드 단계에서 허용 이미지 형식과 최대 10MB를 검증합니다.
- `baby_care_server`도 Tool 실행 전 재검증합니다.
- 별도 컨테이너로 실행 시 공유 임시 디렉터리 또는 Docker Volume을 사용합니다.
- 사용자 입력 경로를 그대로 신뢰하지 않습니다.
- 원본과 분석 결과는 DB에 영구 저장하지 않습니다.
- MCP 실패 시 FastAPI가 남은 임시 파일을 정리합니다.

---

# 1. 개발 목표

백엔드에서 다음 기능을 제공합니다.

- 가짜 사용자 로그인
- 아기 정보 등록·조회·수정
- 수유·수면·배변·성장 기록
- 기록 조회·수정·삭제
- 수유 화면 알림 상태 관리
- 최근 육아 생활 패턴 분석
- 성장 기록과 성장 기준 조회
- 가짜 예방접종 정보 조회
- AI 채팅 요청 처리
- AI 채팅 진행 상태 SSE 실시간 전달
- 채팅 선택지 데이터 반환
- MCP Tool 호출
- 입력 방식별 기록 실행 정책과 STT 기록 승인 상태 관리
- 월령별 육아 정보 RAG 검색
- 실제 소아과·응급실 API 조회
- 기저귀 사진 분석
- 보호자 음성 STT 입력
- Redis 기반 최근 대화·단기 상태 관리
- PostgreSQL 기반 사용자 장기 Memory 관리
- 현재 질문과 관련 있는 Memory 선택 및 개인화 답변
- Memory 저장 전 안전성 검사
- 저장된 Memory 조회·수정·삭제·내보내기
- AI 답변에 사용된 Memory Trace 기록

---

# 2. 기술 구성

| 영역 | 사용 기술 |
| --- | --- |
| 개발 언어 | Python |
| 백엔드 API | FastAPI |
| 채팅 진행 상태 | SSE (`text/event-stream`) |
| 데이터 검증 | Pydantic |
| 데이터베이스 | PostgreSQL |
| 임시 상태·캐시 | Redis |
| RAG | PostgreSQL·pgvector |
| AI Agent | OpenAI API |
| MCP 서버 | Python 기반 MCP |
| 의료기관 | 실제 공공데이터 API |
| 예방접종 | 가짜 JSON 또는 DB |
| API 문서 | Swagger `/docs` |
| 임베딩 | Ollama Embedding |
| STT | OpenAI STT |
| Agent 단기 Memory | Redis |
| Agent 장기 Memory | PostgreSQL `user_memories` |
| Memory 선택·개인화 | Agent Memory Layer |
| Memory Trace | 구조화 로그 |

---

# 3. 전체 백엔드 구조

## 일반 FastAPI 기능

아기 정보 등록·수정, 예방접종 JSON 조회, 수유 알림 상태 관리, 육아 기록 수정·삭제, STT처럼 Agent 판단이 필요하지 않은 기능은 FastAPI가 직접 처리합니다.

```text
클라이언트
→ FastAPI Router
→ Pydantic Schema 검증
→ Service
→ Repository / PostgreSQL / Redis / JSON / 외부 API
→ 공통 응답 반환
```

## AI Agent·MCP 기능

```text
클라이언트
→ FastAPI /api/chat/stream
→ Redis 최근 대화 조회
→ PostgreSQL 사용자 Memory 조회
→ 질문 관련 Memory 선택
→ AI Agent
→ 필요 시 MCP Client
→ baby_care_server 또는 baby_info_server
→ MCP Tool
→ DB·RAG·외부 API
→ Agent 최종 답변
→ Redis 최근 대화 갱신
→ Memory 후보 추출·안전성 검사
→ 필요한 Memory만 PostgreSQL 저장·갱신
```

SSE는 Agent 내부 추론을 노출하지 않고 사용자용 진행 상태만 전달합니다.

---

# 4. 백엔드 폴더 구조

```text
backend/
├─ app/
│  ├─ main.py
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ constants.py
│  │  ├─ api_response.py
│  │  ├─ exceptions.py
│  │  ├─ logging.py
│  │  └─ record_policy.py
│  ├─ routers/
│  │  ├─ auth_router.py
│  │  ├─ baby_router.py
│  │  ├─ care_router.py
│  │  ├─ info_router.py
│  │  ├─ chat_router.py
│  │  ├─ media_router.py
│  │  └─ memory_router.py
│  ├─ schemas/
│  │  ├─ common.py
│  │  ├─ auth.py
│  │  ├─ baby.py
│  │  ├─ care.py
│  │  ├─ info.py
│  │  ├─ chat.py
│  │  ├─ media.py
│  │  └─ memory.py
│  ├─ services/
│  │  ├─ auth_service.py
│  │  ├─ baby_service.py
│  │  ├─ care/
│  │  │  ├─ care_log_service.py
│  │  │  ├─ reminder_service.py
│  │  │  └─ growth_service.py
│  │  ├─ info/
│  │  │  ├─ vaccination_service.py
│  │  │  └─ hospital_service.py
│  │  ├─ agent/
│  │  │  ├─ agent_service.py
│  │  │  ├─ chat_stream_service.py
│  │  │  ├─ tool_call_service.py
│  │  │  ├─ memory_service.py
│  │  │  ├─ memory_selector.py
│  │  │  ├─ memory_safety_service.py
│  │  │  └─ memory_trace_service.py
│  │  └─ media/
│  │     ├─ image_service.py
│  │     └─ speech_service.py
│  ├─ repositories/
│  │  ├─ baby_repository.py
│  │  ├─ care_log_repository.py
│  │  ├─ reminder_repository.py
│  │  └─ memory_repository.py
│  ├─ models/
│  │  ├─ baby.py
│  │  ├─ care_log.py
│  │  ├─ reminder.py
│  │  └─ user_memory.py
│  ├─ prompts/
│  │  ├─ memory_extraction_prompt.txt
│  │  └─ memory_selection_prompt.txt
│  └─ mcp_clients/
│     ├─ baby_care_client.py
│     └─ baby_info_client.py
├─ data/
│  ├─ test_users.json
│  ├─ vaccinations.json
│  └─ growth_reference.json

```

Git에는 실제 `.env`를 올리지 않습니다.

---

# 5. 약속된 값 관리

```python
LOG_TYPES = ["feeding", "sleep", "diaper", "growth"]
INPUT_SOURCES = ["text", "ui", "stt"]
CARE_QUERY_TYPES = ["today", "range", "pattern", "latest_feeding"]
STOOL_RISK_LEVELS = ["none", "attention", "urgent", "emergency"]
FEEDING_TYPES = ["breast", "formula", "mixed"]
GENDERS = ["male", "female"]
REMINDER_STATUSES = ["pending", "confirmed", "snoozed", "skipped"]
REMINDER_ACTIONS = ["confirm", "snooze", "skip"]
VACCINATION_STATUSES = ["completed", "scheduled"]
CHAT_RESPONSE_TYPES = [
    "text",
    "options",
    "record_confirmation",
    "hospital_list",
    "diaper_analysis",
    "stt_record_approval",
    "speech_transcription",
    "out_of_scope",
    "unsupported_feature",
    "clarification_required",
    "policy_blocked",
    "error",
]
```

---

# 6. 필수 식별자

| 키 | 역할 | 생성 위치 | 저장 위치 |
| --- | --- | --- | --- |
| `user_id` | 테스트 보호자 식별 | 테스트 데이터 | DB |
| `baby_id` | 아기 식별 | 백엔드 | DB |
| `session_id` | 현재 AI 대화 식별 | 로그인 API | Redis |
| `message_id` | AI 응답 식별 | Agent | 선택 |
| `log_id` | 육아 기록 식별 | DB | DB |
| `reminder_id` | 화면 알림 식별 | 백엔드 | DB·Redis |
| `request_id` | API 요청 추적 | FastAPI | 로그 |
| `tool_call_id` | Tool 실행 추적 | Agent | Redis·로그 |
| `idempotency_key` | 중복 저장 방지 | 백엔드 | DB·Redis |
| `memory_id` | 장기 Memory 식별 | 백엔드 | PostgreSQL |

UUID 문자열 사용을 권장합니다.

---

# 7. `session_id` 사용 기준

- 사용자별 현재 대화 구분
- 질문과 Tool 호출 연결
- 수유량 선택 단계 기억
- STT 육아 기록 승인 상태 관리
- 오류 요청 추적

Redis 상태와 최근 채팅은 목적을 분리합니다.

| Redis Key | 역할 | TTL |
| --- | --- | --- |
| `session:{user_id}:{session_id}` | 현재 Agent 상태, 처리 단계, 현재 요청 연결 정보 | 1일, Sliding TTL |
| `chat:{user_id}:{session_id}` | 최근 사용자·AI 메시지 최대 8개 | 1일, Sliding TTL |

Redis Key에는 반드시 `user_id`, `session_id`를 포함합니다. `baby_id`, `request_id`, `tool_call_id`가 존재하는 흐름에서는 Redis 값 내부에도 함께 저장하며 조회 시 Key의 식별자와 값 내부 식별자가 일치하는지 다시 확인합니다. 해당 흐름에서 아직 생성되지 않은 식별자는 `null`로 둘 수 있습니다.

이렇게 분리하여 Agent 상태가 바뀔 때 최근 채팅 목록 전체를 다시 저장하지 않습니다.

---

# 8. Pydantic Schema 작성 기준

```python
class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

아기 생년월일 미래 날짜 검증은 Service에서 처리합니다.

---

# 9. 육아 기록 Schema

육아 기록 입력 Schema는 `baby_care_server.record_care_event` Tool 계약과 같은 필드명을 사용합니다.

## 수유 기록

```python
class FeedingDetails(StrictBaseModel):
    feeding_type: str = Field(
        pattern="^(breast|formula|mixed)$",
        examples=["formula"],
    )

    amount_ml: int | None = Field(
        default=None,
        ge=0,
        le=500,
        description=(
            "수유량(ml). 입력되는 경우 0 이상. "
            "0도 Care Server 계약상 유효한 feeding 값이며, "
            "Backend에서는 '미수유' 의미로 별도 재해석하지 않습니다."
        ),
        examples=[100],
    )
```

Backend 처리 원칙:

- `amount_ml < 0` → 입력 거부
- `amount_ml = 0` → MCP 계약상 정상 전달 가능
- `amount_ml = null` → 정상 전달 가능
- Backend는 `0`과 `null`의 의미를 임의로 변환하지 않음
- 사용자가 “오늘 수유하지 않았다”, “먹이려고 했는데 안 먹었다”라고 표현한 경우 `amount_ml=0` feeding 기록을 자동 생성하지 않음

의미 기준:

```text
실제 수유 + 측정량 있음
→ amount_ml > 0

실제 수유 + 측정량 모름
→ amount_ml = null

amount_ml = 0
→ Care Server Schema상 유효한 feeding 값
→ Backend에서 "미수유" 의미로 재정의하지 않음

수유하지 않음
→ feeding 기록 생성 안 함
```

## 수면 기록

```python
class SleepDetails(StrictBaseModel):
    action: str = Field(pattern="^(start|end)$")
```

- 이미 수면 중 `start` → `SLEEP_ALREADY_STARTED`
- 시작 기록 없이 `end` → `SLEEP_START_NOT_FOUND`

## 기저귀 기록

```python
class DiaperDetails(StrictBaseModel):
    urine: bool = False
    stool: bool = False
```

`urine=false`, `stool=false`이면 저장하지 않습니다.

## 성장 기록

```python
class GrowthDetails(StrictBaseModel):
    height_cm: float | None = Field(default=None, gt=0, le=150)
    weight_kg: float | None = Field(default=None, gt=0, le=50)
    head_circumference_cm: float | None = Field(default=None, gt=0, le=100)
```

최소 하나는 입력되어야 합니다.

---

# 10. 공통 API 응답 형식

Frontend ↔ FastAPI 전용 계약입니다.

```json
{
  "success": true,
  "message": "수유 기록이 저장되었습니다.",
  "data": {"log_id": "log-001"},
  "request_id": "req-001"
}
```

---

# 11. API 명세

## 11.1 테스트 로그인

`POST /api/test-login`

## 11.2~11.4 아기 정보

- `POST /api/babies`
- `GET /api/babies/{baby_id}`
- `PATCH /api/babies/{baby_id}`

## 11.5 육아 기록 등록

### `POST /api/care-logs`

텍스트와 UI는 승인 없이 `record_care_event`를 호출합니다. STT만 사용자 승인 후 `confirmed_by_user=true`로 호출합니다.

```text
텍스트 입력 → input_source="text"
버튼·숫자 UI → input_source="ui"
STT 입력 → input_source="stt"
```

### 미수유 자연어 처리

다음 표현은 feeding 이벤트로 만들지 않습니다.

```text
"오늘은 수유를 안 했어."
"먹이려고 했는데 안 먹었어."
```

잘못된 변환:

```json
{
  "event_type": "feeding",
  "amount_ml": 0
}
```

권장 처리:

```text
feeding 기록 생성 없음
```

`amount_ml=0`은 사용자가 명시적으로 구조화 입력한 경우 Care Server 계약대로 전달할 수 있지만, Backend가 이를 “미수유”로 자동 생성하지 않습니다.

## 11.6 육아 기록 조회

### `GET /api/care-logs`

`today`, `range`를 사용합니다. `range`는 `start_date`, `end_date`를 `YYYY-MM-DD`로 전달하고 양끝을 포함합니다.

## 11.7~11.8 기록 수정·삭제

FastAPI가 직접 처리합니다.

- `PATCH /api/care-logs/{log_id}`
- `DELETE /api/care-logs/{log_id}`

## 11.9 생활 패턴 조회

### `GET /api/care-patterns/{baby_id}?days=7`

```text
get_care_records(
    baby_id=baby_id,
    query_type="pattern",
    days=days
)
```

- `days`: 기본 7, 범위 1~30
- 충분 기준: 유효 기록 5건 이상 + 기록일 3일 이상
- 계산 불가 평균은 `null`
- FastAPI는 Care Server가 계산한 패턴을 다시 계산하거나 보정하지 않음
- `amount_ml=0`인 기록을 Backend에서 임의 제외하지 않음

## 11.10 성장 정보 조회

`GET /api/growth/{baby_id}`

Care Server 성장 기록과 Backend `growth_reference.json`을 조합합니다.

## 11.11 수유 알림 조회

### `GET /api/reminders/feeding/{baby_id}`

마지막 확정 수유 기록은 다음으로 조회합니다.

```text
get_care_records(
    baby_id=baby_id,
    query_type="latest_feeding"
)
```

Backend는 반환된 `latest_feeding`을 임의로 재필터링하지 않습니다.

따라서 “미수유”를 `amount_ml=0` feeding으로 자동 생성하지 않습니다.

예:

```text
09:00 분유 100ml
13:00 수유하지 않음

→ 13:00 feeding 기록 없음
→ latest_feeding = 09:00
```

## 11.12 알림 상태 변경

`PATCH /api/reminders/{reminder_id}`

지원 action:

```text
confirm
snooze
skip
```

## 11.13 예방접종 조회

`GET /api/vaccinations/{baby_id}`

FastAPI `vaccinations.json` 목데이터 사용.

## 11.14 의료기관 검색

`GET /api/hospitals/search`

`pediatric` 또는 `emergency`에 따라 `baby_info_server` Tool 선택.

## 11.15 기저귀 사진 분석

`POST /api/images/diaper-analysis`

FastAPI가 업로드 검증 후 `image_path`를 Care Server에 전달합니다.

## 11.16 AI 채팅

- `POST /api/chat`
- `POST /api/chat/stream`

## 11.17 선택지를 포함한 AI 응답

Frontend는 일반 오류와 범위 밖·미지원·추가 확인 필요·정책 차단을 구분할 수 있도록 다음 응답 타입을 사용합니다.

```python
CHAT_RESPONSE_TYPES = [
    "text",
    "options",
    "record_confirmation",
    "hospital_list",
    "diaper_analysis",
    "stt_record_approval",
    "speech_transcription",
    "out_of_scope",
    "unsupported_feature",
    "clarification_required",
    "policy_blocked",
    "error",
]
```

- `out_of_scope`: 육아 서비스 범위를 벗어난 요청
- `unsupported_feature`: 서비스 범위에는 가깝지만 현재 구현하지 않은 기능 요청
- `clarification_required`: Tool 실행 전에 필수 정보가 부족하여 사용자 확인이 필요한 경우
- `policy_blocked`: 다른 사용자 데이터 접근, 안전 정책 위반 등 실행을 차단해야 하는 요청
- `error`: 실제 처리 실패나 서버 오류

---

# 12. 채팅 진행 상태 SSE

SSE는 MCP Streamable HTTP와 별개이며 사용자용 진행 상태만 전달합니다.

```text
received
loading_context
analyzing_request
using_tool
generating_answer
completed
error
```

---

# 13. 대화 상태 관리

```python
CHAT_STATES = [
    "waiting",
    "amount_selection",
    "waiting_stt_approval",
    "saved",
    "snoozed",
    "skipped",
]
```

---

# 14. 기록 입력 방식별 실행 정책

```python
RECORD_APPROVAL_POLICY = {
    "text": False,
    "ui": False,
    "stt": True,
}
```

- 텍스트: 즉시 저장
- UI: 즉시 저장
- STT: 승인 후 저장
- 기저귀 사진 분석: 업로드 행동 자체를 실행 의사로 봄

Agent 자연어 해석 규칙:

```text
"분유 100ml 먹였어"
→ feeding, amount_ml=100

"모유 수유했어"
→ feeding, amount_ml=null

"오늘 수유 안 했어"
→ feeding 기록 생성하지 않음
```

---

# 15. STT 육아 기록 승인 처리

STT로 생성된 실제 육아 기록만 승인 Snapshot을 생성합니다.

미수유 표현 예:

```text
"분유 먹이려고 했는데 하나도 안 먹었어."
```

이 경우:

```text
feeding 기록 없음
→ stt_record_approval 생성하지 않음
→ DB 저장 없음
```

실제 feeding 기록이 있는 경우에만:

```text
STT
→ Snapshot
→ Redis stt_approval:{user_id}:{session_id}:{tool_call_id}
→ 사용자 승인
→ Snapshot 재검증
→ record_care_event(input_source="stt", confirmed_by_user=true)
→ FastAPI가 Tool 결과를 Frontend에 반환
```

### 승인 후 처리 방식

이 프로젝트는 **B 방식: 승인 후 Agent Loop를 재개하지 않고 Tool만 실행한 뒤 FastAPI가 결과를 반환**하는 구조로 고정합니다.

따라서 STT 승인 Snapshot에는 OpenAI Agent 실행 재개용 `response_id`, `next_step`을 저장하지 않습니다. 승인 이후 동일한 Agent 응답을 이어서 생성할 필요가 있는 기능을 나중에 추가할 때만 A 방식으로 확장합니다.

권장 Snapshot:

```json
{
  "user_id": "user-001",
  "baby_id": "baby-001",
  "session_id": "session-001",
  "request_id": "req-001",
  "tool_call_id": "tool-call-001",
  "pending_call": {
    "name": "record_care_event",
    "arguments": {}
  },
  "approval_snapshot": {},
  "idempotency_key": "session-001-tool-call-001",
  "status": "waiting_stt_approval",
  "expires_at": "2026-09-04T15:10:00+09:00"
}
```

승인 처리 시 다음을 검증합니다.

- Key의 `user_id`, `session_id`, `tool_call_id`와 Snapshot 내부 값이 모두 일치하는지 확인
- 현재 요청의 `baby_id`, `request_id`가 Snapshot과 연결된 값인지 확인
- `expires_at`이 지나지 않았는지 확인
- `status="waiting_stt_approval"`인지 확인
- 실제 실행할 Tool 이름·인자가 `pending_call` 및 `approval_snapshot`과 일치하는지 확인
- 이미 처리된 Snapshot을 다시 실행하지 않음
- 실제 Tool 실행에는 Snapshot의 동일한 `idempotency_key`를 사용

승인·거절·중복 승인 결과는 `trace:{user_id}:{session_id}:{request_id}`에도 실행 사실만 기록합니다. 모델의 내부 추론 내용은 저장하지 않습니다.

---

# 16. 중복 저장 방지

동일 `idempotency_key` 재호출은 새 INSERT 없이 기존 결과와 `duplicated=true`를 반환합니다.

---

# 17. MCP 서버 구성

운영 MCP 서버는 2개입니다.

## `baby_care_server`

```text
record_care_event
get_care_records
analyze_infant_stool
```

## `baby_info_server`

```text
search_pediatric_hospitals
search_emergency_hospitals
search_feeding_guide
search_sleep_guide
search_weaning_guide
search_development_guide
search_safety_guide
```

---

# 18. MCP Tool Schema

## 18.1 `baby_care_server`

### 18.1.1 `record_care_event`

허용 `event_type`:

```text
feeding
sleep
diaper
growth
```

허용 `input_source`:

```text
text
ui
stt
```

수유량은 값이 입력되는 경우 `0` 이상이어야 합니다.

`amount_ml=0`은 Care Server Tool Schema에서 허용되는 유효한 입력값입니다. FastAPI는 이를 임의로 “수유하지 않음”이라는 별도 상태로 재정의하지 않습니다.

사용자가 특정 날짜 또는 시점에 수유하지 않았다는 사실만 표현한 경우에는 `amount_ml=0` feeding 기록을 자동 생성하지 않고 새로운 feeding 기록을 생성하지 않습니다.

### 18.1.2 `get_care_records`

허용 `query_type`:

```text
today
range
pattern
latest_feeding
```

- `range`는 한국 날짜 기준 양끝 포함
- 기록 없음은 정상 성공
- DB 컬럼은 `log_type`, MCP 필드는 `event_type`
- 패턴 충분 기준은 유효 기록 5건 이상 + 기록일 3일 이상
- 계산 불가능한 평균은 `null`

### 18.1.3 `analyze_infant_stool`

FastAPI는 업로드 검증과 임시 파일 관리를 담당하고, Care Server는 Vision·규칙·RAG Workflow를 담당합니다.

위험 수준:

```text
none
attention
urgent
emergency
```

품질 부족은 `success=true`, `is_analyzable=false`이며 RAG 결과 없음도 정상 성공입니다.

## 18.2 `baby_info_server` 의료기관 Tool

- `search_pediatric_hospitals`
- `search_emergency_hospitals`

입력: `region`, `page`, `limit`

## 18.3 `baby_info_server` 육아 지식 RAG Tool

- `search_feeding_guide`
- `search_sleep_guide`
- `search_weaning_guide`
- `search_development_guide`
- `search_safety_guide`

근거 부족은 `success=true`, `sources=[]`, `confidence=low`로 처리합니다.

## 18.4 FastAPI MCP Client 처리

Tool별 성공/실패 Schema를 검증하며 어느 Schema에도 맞지 않으면 `INVALID_MCP_RESPONSE`입니다.

---

# 19. DB 구조

DB 테이블은 총 6개입니다.

```text
babies
care_logs
reminder_settings
documents
document_chunks
user_memories
```

## 테이블 담당

| DB 테이블 | 담당 |
| --- | --- |
| `babies` | FastAPI Backend |
| `care_logs` | baby_care_server + FastAPI |
| `reminder_settings` | FastAPI Backend |
| `documents` | baby_info_server |
| `document_chunks` | baby_info_server |
| `user_memories` | FastAPI Agent Memory Layer |

개발 단계에서는 각자 로컬 PostgreSQL을 사용하고, 최종 통합에서는 하나의 PostgreSQL에 6개 테이블을 구성합니다.

ID는 `VARCHAR(100)`, 날짜·시간은 `TIMESTAMPTZ`, RAG `category`는 `documents`에 저장합니다.

---

# 20. 데이터 저장소 역할

| 영역 | 사용 기술 |
| --- | --- |
| 데이터베이스 | PostgreSQL |
| 벡터 검색 | PostgreSQL + pgvector |
| DB 연결 | SQLAlchemy 또는 psycopg |
| 임시 상태 | Redis |
| 임베딩 | Ollama Embedding |

---

# 21. Redis 사용 범위

Redis Key는 사용자·세션 범위를 명확히 분리하여 다른 사용자의 상태와 섞이지 않도록 합니다.

| Redis Key | 저장 내용 | TTL |
| --- | --- | --- |
| `session:{user_id}:{session_id}` | 현재 Agent 상태, 처리 단계, 현재 요청 연결 정보 | 1일, Sliding TTL |
| `chat:{user_id}:{session_id}` | 최근 사용자·AI 메시지 최대 8개 | 1일, Sliding TTL |
| `reminder:{user_id}:{baby_id}` | 현재 수유 알림 상태 | 1일 |
| `stt_approval:{user_id}:{session_id}:{tool_call_id}` | STT 육아 기록 승인 Snapshot | 10분 |
| `idempotency:{user_id}:{session_id}:{key}` | FastAPI 중복 처리 결과 | 1일 |
| `trace:{user_id}:{session_id}:{request_id}` | Agent 실행 단계·Tool 선택·승인·MCP 결과·최종 상태 | 1일 |

Redis 값 내부에는 가능한 경우 다음 식별자를 함께 저장합니다.

```text
user_id
baby_id
session_id
request_id
tool_call_id
```

아직 생성되지 않았거나 해당 상태에 적용되지 않는 식별자는 `null`을 허용합니다. Redis 조회 시 Key에 포함된 `user_id`, `session_id`, `baby_id`, `tool_call_id`와 값 내부 식별자가 일치하는지 다시 검사하고, 불일치하면 데이터를 사용하지 않습니다.

`idempotency:{user_id}:{session_id}:{key}`는 FastAPI Redis namespace입니다. `care_logs.idempotency_key`의 DB `UNIQUE` 계약과 MCP Tool에 전달하는 `idempotency_key` 자체는 기존 계약을 그대로 유지합니다.

### Agent 실행 Trace

Agent 실행 Trace는 다음 Key에 저장합니다.

```text
trace:{user_id}:{session_id}:{request_id}
```

저장 예시:

```json
{
  "request_id": "req-001",
  "user_id": "user-001",
  "session_id": "session-001",
  "baby_id": "baby-001",
  "tool_call_id": "tool-call-001",
  "selected_tools": ["record_care_event"],
  "approval_status": "approved",
  "mcp_status": "success",
  "status": "success",
  "elapsed_ms": 920,
  "error_code": null
}
```

Trace에는 실제로 발생한 실행 단계만 저장합니다.

- Agent가 선택한 Tool
- Tool 실행 성공·실패
- 승인 대기·승인·거절
- MCP 서버 호출 성공·실패 및 표준화된 결과 상태
- 전체 처리 시간
- 최종 상태와 오류 코드

모델의 Chain-of-Thought, 내부 추론 원문, 전체 Prompt, 전체 Memory Context는 저장하지 않습니다.

육아 기록과 아기 정보는 PostgreSQL에 영구 저장합니다.

---

# 22. 외부 API 처리

소아과·응급실 공공데이터 API 호출은 `baby_info_server`가 전담합니다. FastAPI는 공공데이터 API Key와 Base URL을 보유하지 않습니다.

---

# 23. 공공데이터 필드 변환

원본 필드를 프로젝트 형식으로 바꾸는 작업은 `baby_info_server` 내부 의료기관 Service가 담당합니다.

소아과 주요 필드:

```text
hospital_name
address
phone
operating_hours
```

응급실 주요 필드:

```text
hospital_name
address
phone
emergency_level
```

---

# 24. 예방접종 처리

예방접종은 FastAPI의 로컬 목데이터 `vaccinations.json`을 사용합니다. 실제 접종 이력 API는 사용하지 않습니다.

---

# 25. 성장 기준 처리

성장 기록은 Care Server에서 조회하고 성장 기준은 FastAPI `growth_reference.json`을 사용합니다. 두 값을 `growth_service.py`에서 조합합니다.

---

# 26. 기저귀 분석 처리

FastAPI는 업로드·임시파일·MCP 호출·실패 시 정리를 담당하고, `baby_care_server`는 실제 Workflow 분석을 담당합니다.

---

# 27. 환경변수·서버 연결 원칙

- Backend에서 MCP 서버 주소를 환경변수로 관리합니다.
- Docker 컨테이너 간 통신에서 `127.0.0.1`을 다른 컨테이너 주소로 사용하지 않습니다.
- 실제 `.env`는 GitHub에 올리지 않고 `.env.example`만 공유합니다.

---

# 28. 오류 코드

| HTTP | 오류 코드 | 의미 |
| --- | --- | --- |
| 400 | `INVALID_REQUEST` | 잘못된 요청 |
| 404 | `BABY_NOT_FOUND` | 아기 정보 없음 |
| 404 | `CARE_LOG_NOT_FOUND` | 수정·삭제 대상 기록 없음 |
| 400 | `INVALID_DATE_RANGE` | 시작일이 종료일보다 늦음 |
| 409 | `STT_CONFIRMATION_REQUIRED` | 승인되지 않은 STT 저장 요청 |
| 422 | `INVALID_CARE_EVENT` | 기록 종류별 필수값 오류 |
| 409 | `SLEEP_ALREADY_STARTED` | 수면 중복 시작 |
| 409 | `SLEEP_START_NOT_FOUND` | 시작 기록 없는 수면 종료 |
| 404 | `IMAGE_NOT_FOUND` | 임시 이미지 없음 |
| 400 | `INVALID_IMAGE_PATH` | 허용 폴더 밖의 이미지 경로 |
| 415 | `UNSUPPORTED_IMAGE_TYPE` | 지원하지 않는 이미지 형식 |
| 413 | `IMAGE_TOO_LARGE` | 이미지 크기 초과 |
| 502 | `VISION_API_ERROR` | Vision API 실패 |
| 503 | `RAG_SERVICE_ERROR` | Care Server stool RAG 실패 |
| 401 | `SESSION_INVALID` | 세션이 없거나 만료됨 |
| 404 | `APPROVAL_NOT_FOUND` | 승인할 Snapshot이 없음 |
| 410 | `APPROVAL_EXPIRED` | 승인 Snapshot 유효시간 만료 |
| 409 | `APPROVAL_MISMATCH` | 승인 Snapshot과 실제 실행 Tool·인자가 불일치 |
| 409 | `APPROVAL_ALREADY_PROCESSED` | 승인 버튼 중복 실행 또는 이미 처리된 Snapshot |
| 403 | `TOOL_NOT_ALLOWED` | 허용되지 않은 Tool 실행 요청 |
| 500 | `MAX_AGENT_STEPS_EXCEEDED` | Agent 최대 반복 횟수 초과 |
| 502 | `MODEL_ERROR` | OpenAI Agent 모델 호출 실패 |
| 400 | `OUT_OF_SCOPE` | 육아 서비스 범위 밖 요청 |
| 501 | `UNSUPPORTED_FEATURE` | 현재 구현하지 않은 기능 요청 |
| 403 | `POLICY_BLOCKED` | 다른 사용자 접근·지침 무시 요청 등 정책상 차단 |
| 422 | `VALIDATION_ERROR` | FastAPI 검증 실패 |
| 424 | `EXTERNAL_API_ERROR` | 공공데이터 API 오류 |
| 429 | `RATE_LIMIT_EXCEEDED` | 호출량 초과 |
| 400 | `MEMORY_NOT_ALLOWED` | 저장 불가 Memory |
| 404 | `MEMORY_NOT_FOUND` | Memory 없음 |
| 409 | `MEMORY_CONFLICT` | Memory 동시 수정 충돌 |
| 422 | `INVALID_MEMORY` | Memory 형식 오류 |
| 502 | `INVALID_MCP_RESPONSE` | MCP 응답 Schema 불일치 |
| 502 | `ANSWER_GENERATION_FAILED` | RAG 후 답변 생성 실패 |
| 500 | `INTERNAL_SERVER_ERROR` | 내부 서버 오류 |
| 503 | `MCP_SERVER_UNAVAILABLE` | MCP 서버 연결 실패 |
| 503 | `RAG_SERVICE_UNAVAILABLE` | Info Server RAG 계층 사용 불가 |

중복 `idempotency_key`는 오류가 아닙니다.

Agent 설계 문서에서 MCP 서버 연결·호출 자체가 불가능한 경우의 오류명은 별도 `MCP_SERVER_ERROR`를 만들지 않고 기존 `MCP_SERVER_UNAVAILABLE`로 통일합니다.

---

# 29. 로그 설계

기록:

```text
request_id
session_id
user_id
baby_id
tool_call_id
tool_name
input_source
approval_status
status
elapsed_ms
error_code
memory_retrieved_count
memory_used_count
memory_created_count
memory_updated_count
memory_trace_id
```

### 29.1 Agent 실행 Trace 저장 위치

구조화 로그와 별도로, 한 요청의 실행 흐름을 짧게 조회할 수 있도록 Redis `trace:{user_id}:{session_id}:{request_id}`에 TTL 1일로 저장합니다. 이 Trace는 Tool 선택·승인 상태·MCP 호출 상태·처리 시간·최종 상태만 기록하며 내부 추론 원문은 기록하지 않습니다.

기록하지 않음:

- API Key
- DB·Redis 접속정보
- 기저귀 이미지 원본
- 음성 원본
- 개인 건강정보 전체
- 민감 Memory 원문
- 전체 Memory Context
- 전체 대화 원문

---

# 30. 테스트 데이터

| 사용자 | 아기 조건 | 특징 |
| --- | --- | --- |
| 서아 보호자 | 생후 31일 | 분유, 마지막 수유 3시간 전 |
| 민준 보호자 | 생후 6개월 | 이유식 시작 |
| 지우 보호자 | 생후 18개월 | 땅콩 알레르기 |

---

# 31. 필수 테스트 항목

## Care / 기록

- 존재하지 않는 `baby_id`
- 약속되지 않은 문자열 입력
- 미래 생년월일
- `amount_ml=0`인 수유 기록이 MCP Schema상 정상 전달·저장되는지
- `amount_ml<0`인 경우 거부
- “오늘 수유 안 했어”가 `amount_ml=0` feeding으로 자동 변환되지 않는지
- “먹이려고 했는데 안 먹었어”가 feeding 기록으로 저장되지 않는지
- 미수유 표현 후 `latest_feeding`이 이전 실제 수유 기록으로 유지되는지
- 미수유 표현 때문에 수유 알림 기준 시간이 변경되지 않는지
- `amount_ml=0`을 사용자가 명시적으로 구조화 입력한 경우 Care Server 계약대로 전달 가능한지
- Backend가 Care Server `pattern` 결과를 임의 재계산하지 않는지
- 수면 중복 시작·시작 없는 종료
- 기저귀 `urine=false`, `stool=false`
- 성장값 모두 없음
- `range` 날짜 검증
- `today`, `range` 빈 결과 정상 처리
- `latest_feeding=null` 정상 처리
- 패턴 충분 기준 5건 + 3일
- 계산 불가 평균 `null`
- 중복 `idempotency_key` → `duplicated=true`

## 이미지 / RAG

- 잘못된 이미지 형식·용량 초과
- 품질 부족 시 `success=true`, `is_analyzable=false`
- RAG 결과 없음
- Vision 성공 + RAG 실패 시 `warnings`
- Vision API 실패
- stool 이외 카테고리 접근 차단

## STT

- 일반 질문은 승인 없이 답변
- 실제 육아 기록 요청만 승인 Snapshot 생성
- 미수유 발화는 Snapshot 생성하지 않음
- 승인/거부/중복 승인 처리
- 승인 Snapshot과 실제 Tool 인자 불일치 시 실행 금지

## SSE

- 진행 단계 순서
- Tool 없는 질문에서 `using_tool` 생략
- 오류 Event 전송 후 종료
- 내부 Prompt·Memory 원문·Stack Trace 미노출

## DB 통합

- 6개 테이블 생성
- ID `VARCHAR(100)` 통일
- 시간 `TIMESTAMPTZ`
- Backend / Care / Info Server 동일 PostgreSQL 연결
- 아기 등록 → 기록 저장·조회 → 패턴 → 수유 알림 → Memory → RAG → 변 분석 통합 흐름

---

# 32. STT 음성 입력

보호자 음성을 텍스트로 변환하여 AI 채팅 입력으로 사용합니다.

## 처리 흐름

```text
보호자 음성 업로드
→ 파일 검증
→ STT API
→ transcript
→ Agent 의도 판단
   ├─ 일반 질문 → 승인 없이 답변
   ├─ 실제 육아 기록 → Snapshot → 승인 → record_care_event
   └─ 미수유 표현 → 저장할 이벤트 없음 → 승인 없음
```

## STT 처리 기준

- MP3·WAV·M4A·WebM
- 최대 20MB
- UUID 임시 파일명
- 처리 후 음성 원본 삭제
- 원본 DB·로그 저장 금지
- 승인 전 Snapshot은 Redis `stt_approval:{user_id}:{session_id}:{tool_call_id}`
- 승인 중복은 `idempotency_key`로 한 번만 저장
- 아기 울음소리 분석은 구현하지 않음

---

# 33. 수유 알림 최종 설계

보호자는 특정 날짜·시각을 예약하지 않고 **수유 알림 간격**만 설정합니다. DB에는 화면 문구가 아니라 분 단위 정수로 저장합니다.

```python
class FeedingReminderSettings(StrictBaseModel):
    feeding_interval_minutes: int = Field(ge=30, le=720)
```

입력 규칙:

- 빠른 선택: 2시간(120분), 2시간 30분(150분), 3시간(180분), 3시간 30분(210분)
- 직접 설정: `시간 + 분` 입력을 총 분으로 변환하여 저장
- 최소 30분, 최대 12시간(720분)
- 날짜와 특정 시각을 직접 지정하는 알림 기능은 구현하지 않음

DB 저장 예:

```json
{
  "feeding_interval_minutes": 165
}
```

다음 알림 시간은 마지막으로 확정된 수유 시각에 `feeding_interval_minutes`를 더해 계산합니다.

```text
실제 record_care_event 실행
→ baby_care_server care_logs 저장
→ get_care_records(query_type="latest_feeding")
→ reminder_settings.feeding_interval_minutes 조회
→ latest_feeding.recorded_at + feeding_interval_minutes
→ Redis reminder:{user_id}:{baby_id}
```

- `10분 후`: 기록 생성 없이 현재 시각 + 10분, `snoozed`
- `건너뛰기`: 마지막 수유 변경 없이 `skipped`
- `수유했어요`: 실제 수유 기록이 저장된 경우만 다음 알림 재계산
- “수유하지 않음” 표현은 feeding 기록을 만들지 않으므로 알림 기준 시각을 변경하지 않음
- `amount_ml=0`을 Backend가 미수유로 자동 생성하지 않음
- 직접 설정은 날짜·시간 예약이 아니라 간격 설정이므로 기존 제외 범위와 충돌하지 않음

---

# 34. Agent Memory 최종 설계

Memory는 별도 운영 MCP 서버가 아니라 FastAPI Baby Agent 내부 계층입니다.

## 34.1 저장소별 역할

| 구분 | 저장소 | 목적 |
| --- | --- | --- |
| Business Data | PostgreSQL | 아기 정보·육아 기록 |
| RAG Knowledge | PostgreSQL + pgvector | 육아 지식 검색 |
| Short-term Memory | Redis | 최근 8개 대화·임시 상태 |
| Long-term Memory | PostgreSQL `user_memories` | 장기 사용자 맥락 |

```text
"오늘 아침 몇 시에 수유했어?"
→ Memory가 아니라 care_logs / get_care_records

"앞으로 답변은 짧게 해줘."
→ user_memories
```

## 34.2 Short-term Memory

Redis Short-term Memory는 상태와 채팅을 분리합니다.

- `session:{user_id}:{session_id}`: 현재 Agent 상태·처리 단계, TTL 1일, Sliding TTL
- `chat:{user_id}:{session_id}`: 최근 사용자·AI 메시지 최대 8개, TTL 1일, Sliding TTL

두 Key 모두 사용자·세션 식별자를 기준으로 격리하고 조회 시 값 내부의 식별자도 다시 검증합니다.

## 34.3 Long-term Memory 저장 기준

답변 스타일·길이·단위 선호·과거 결정 등 이후 대화에서 재사용 가치가 있는 정보만 저장합니다. 정확한 육아 기록은 `user_memories`가 아니라 `care_logs`에 저장합니다.

## 34.4 Memory 안전성

API Key·비밀번호·카드정보 등 민감정보를 Memory에 저장하지 않습니다. 저장 전 allowlist 및 안전성 검사를 수행합니다.

## 34.5 Memory 선택

현재 질문과 관련 있는 Memory만 선택하고 최대 3개 정도를 Agent Context에 넣습니다. 관련 없는 Memory는 넣지 않습니다.

---

# 최종 구현 기준

- 운영 MCP 서버는 `baby_care_server`, `baby_info_server` 2개
- Care Server Tool 계약은 고정
- Backend는 Care Server의 Tool/Schema/Response 계약을 그대로 따름
- `amount_ml >= 0`, `null` 허용
- `amount_ml=0`은 Care Server 계약상 유효한 feeding 값이지만 Backend가 “미수유”로 재정의하지 않음
- “수유하지 않음”은 feeding 기록을 생성하지 않는 것으로 처리
- Care Server의 `pattern`, `latest_feeding` 결과를 Backend가 임의 재계산·재필터링하지 않음
- STT만 기록 저장 전 승인
- 텍스트·UI 기록은 승인 없이 저장
- 수유 알림은 FastAPI가 `latest_feeding` 기준으로 계산
- Memory는 Agent 내부 계층으로 유지
- Redis Key는 `user_id`·`session_id`를 포함하여 사용자·세션별로 격리
- Agent 상태는 `session:{user_id}:{session_id}`, 최근 대화는 `chat:{user_id}:{session_id}`로 분리
- Agent 실행 Trace는 `trace:{user_id}:{session_id}:{request_id}`에 TTL 1일로 저장하며 내부 추론은 저장하지 않음
- STT 승인은 B 방식으로 처리: 승인 후 Agent Loop 재개 없이 Snapshot 검증 → Tool 실행 → FastAPI 결과 반환
- 채팅 응답은 범위 밖·미지원·추가 확인 필요·정책 차단 타입을 일반 오류와 구분
- Agent·승인 관련 오류 코드를 공통 오류 표에 포함하고 MCP 연결 오류는 `MCP_SERVER_UNAVAILABLE`로 통일
- 수유 알림 간격은 빠른 선택 또는 직접 설정을 지원하며 DB에는 `feeding_interval_minutes`(30~720)로 저장
- 개발 단계는 각자 로컬 PostgreSQL, 최종 통합은 하나의 PostgreSQL 6개 테이블
- 실제 `.env`는 Git에 올리지 않음
