# AI 육아 도우미 프론트엔드 API 계약표

> 프론트엔드(Streamlit)와 FastAPI 사이의 연동 기준입니다. 아래에서 **확정**은 기존 기획 문서에 명시된 내용이며, **백엔드 확정 필요**는 구현 전에 담당자와 정해야 하는 항목입니다.

## 1. 공통 규칙

### 기본 URL

```text
BACKEND_API_URL=http://localhost:8000
```

`frontend/api.py`는 위 URL 뒤에 아래 경로를 붙여 요청합니다.

### 공통 성공 응답

```json
{
  "success": true,
  "message": "수유 기록이 저장되었습니다.",
  "data": {},
  "request_id": "req-001"
}
```

- `success`: 성공 여부
- `message`: 사용자에게 보여 줄 수 있는 요약 문구
- `data`: API별 실제 결과
- `request_id`: 오류 문의·추적용 식별자

### 공통 실패 처리

- `success=false` 또는 HTTP 오류이면 `message`를 우선 표시합니다.
- `request_id`가 있으면 “문의 시 참고 번호”로만 표시합니다.
- API Key, 내부 URL, SQL, Stack Trace는 화면에 표시하지 않습니다.
- 422 입력 오류는 해당 입력칸 가까이에 표시하고, 일시적 서버 오류는 재시도 버튼을 제공합니다.

### 식별자와 세션

로그인 뒤 프론트엔드는 아래 값을 `st.session_state`에 보관합니다.

```python
user_id
baby_id
session_id
```

**백엔드 확정 필요:** 각 API에서 이 값을 body, query parameter, header 중 어느 방식으로 받는지와 로그인 응답의 정확한 `data` 구조.

---

## 2. API 목록

| 화면 | 함수 예시 | HTTP | 경로 | 상태 |
| --- | --- | --- | --- | --- |
| 로그인 | `test_login` | POST | `/api/test-login` | 경로 확정 |
| 아기 등록 | `create_baby` | POST | `/api/babies` | 경로 확정 |
| 아기 조회 | `get_baby` | GET | `/api/babies/{baby_id}` | 경로 확정 |
| 아기 수정 | `update_baby` | PATCH | `/api/babies/{baby_id}` | 경로 확정 |
| 기록 저장 | `create_care_log` | POST | `/api/care-logs` | 경로·규칙 확정 |
| 기록 조회 | `get_care_logs` | GET | `/api/care-logs` | 경로·조회 종류 확정 |
| 기록 수정 | `update_care_log` | PATCH | `/api/care-logs/{log_id}` | 경로 확정 |
| 기록 삭제 | `delete_care_log` | DELETE | `/api/care-logs/{log_id}` | 경로 확정 |
| 패턴 조회 | `get_care_pattern` | GET | `/api/care-patterns/{baby_id}` | 경로·파라미터 확정 |
| 성장 조회 | `get_growth` | GET | `/api/growth/{baby_id}` | 경로 확정 |
| 수유 알림 조회 | `get_feeding_reminder` | GET | `/api/reminders/feeding/{baby_id}` | 경로 확정 |
| 알림 상태 변경 | `update_reminder` | PATCH | `/api/reminders/{reminder_id}` | 경로·action 확정 |
| 예방접종 조회 | `get_vaccinations` | GET | `/api/vaccinations/{baby_id}` | 경로 확정 |
| 병원 검색 | `search_hospitals` | GET | `/api/hospitals/search` | 경로·검색 기준 확정 |
| 기저귀 사진 분석 | `analyze_diaper_image` | POST | `/api/images/diaper-analysis` | 경로·결과 구조 확정 |
| 일반 채팅 | `send_chat` | POST | `/api/chat` | 경로 확정 |
| 스트리밍 채팅 | `stream_chat` | POST | `/api/chat/stream` | 경로·SSE 상태 확정 |

---

## 3. 로그인과 아기 정보

### 테스트 로그인

```http
POST /api/test-login
```

**프론트 입력:** 선택한 테스트 사용자 식별값

**백엔드 확정 필요:** 요청 필드명(`user_id` 등), 로그인 성공 시 반환하는 보호자·아기·세션 데이터 전체 구조.

**프론트 처리:**

1. 성공 시 `user_id`, `baby_id`, `session_id`를 세션에 저장합니다.
2. `baby_id`가 없으면 `profile_page.py`의 아기 등록 폼을 엽니다.
3. 있으면 홈으로 이동합니다.

### 아기 등록·조회·수정

```http
POST  /api/babies
GET   /api/babies/{baby_id}
PATCH /api/babies/{baby_id}
```

아기 입력 필드 계약:

```json
{
  "baby_name": "서아",
  "birth_date": "2026-08-03",
  "gender": "female",
  "current_weight_kg": 4.2,
  "current_height_cm": 54.0,
  "feeding_type": "formula",
  "allergies": ["계란"]
}
```

| 필드 | 필수 | 검증 |
| --- | --- | --- |
| `baby_name` | O | 1~30자 |
| `birth_date` | O | 미래 날짜 불가, `YYYY-MM-DD` |
| `gender` | O | 백엔드 허용값만 사용 |
| `feeding_type` | O | `breast`, `formula`, `mixed` 중 하나 |
| `current_weight_kg` | X | 입력 시 0 초과 |
| `current_height_cm` | X | 입력 시 0 초과 |
| `allergies` | X | 보호자 직접 입력 목록 |

---

## 4. 육아 기록

### 기록 저장

```http
POST /api/care-logs
```

공통 요청 형태:

```json
{
  "baby_id": "baby-001",
  "event_type": "feeding",
  "input_source": "ui",
  "recorded_at": "2026-09-04T14:30:00+09:00",
  "idempotency_key": "session-001-ui-unique-key"
}
```

`event_type`는 `feeding`, `sleep`, `diaper`, `growth` 중 하나입니다. `input_source`는 `ui`, `text`, `stt` 중 하나입니다.

| 유형 | 추가 필드 | 검증·처리 규칙 |
| --- | --- | --- |
| 수유 `feeding` | `feeding_type`, `amount_ml` | 방식은 `breast`/`formula`/`mixed`, 양은 입력 시 0 이상 |
| 수면 `sleep` | `action` | `start`/`end`; 중복 시작, 시작 없는 종료는 오류 |
| 배변 `diaper` | `urine`, `stool`, 색상·형태·메모(선택) | `urine` 또는 `stool` 중 하나는 `true` |
| 성장 `growth` | `weight_kg`, `height_cm`, `head_circumference_cm` | 하나 이상 입력, 모든 입력값 0 초과 |

입력 출처별 저장 규칙:

| `input_source` | 프론트 처리 |
| --- | --- |
| `ui` | 즉시 저장 |
| `text` | 즉시 저장 |
| `stt` | 승인 전 저장 금지, 승인 후 `confirmed_by_user=true`일 때만 저장 |

중요: “수유하지 않았어”, “먹이려 했는데 안 먹었어”는 수유 기록으로 만들지 않습니다. 이 문장을 `amount_ml=0`인 기록으로 자동 변환해서는 안 됩니다.

동일한 버튼 재클릭에도 한 번만 저장되도록 같은 요청에는 동일 `idempotency_key`를 사용합니다. 중복 처리 응답은 새 기록을 만들지 않고 기존 결과와 `duplicated=true`를 반환할 수 있습니다.

### 기록 조회

```http
GET /api/care-logs
```

조회 종류:

| `query_type` | 필수 파라미터 | 결과 |
| --- | --- | --- |
| `today` | `baby_id` | 오늘 기록 목록 |
| `range` | `baby_id`, `start_date`, `end_date` | 양끝 포함 기간 기록 목록 |
| `pattern` | `baby_id`, `days` | 패턴 데이터 |
| `latest_feeding` | `baby_id` | 마지막 확정 수유 기록 |

기간 날짜는 `YYYY-MM-DD` 형식입니다. 기록이 없어도 오류가 아니며 `records=[]` 또는 `latest_feeding=null`을 표시합니다.

기록 한 건 표시 구조:

```json
{
  "log_id": "log-001",
  "baby_id": "baby-001",
  "event_type": "feeding",
  "recorded_at": "2026-09-04T14:00:00+09:00",
  "details": {
    "feeding_type": "formula",
    "amount_ml": 100
  }
}
```

### 기록 수정·삭제

```http
PATCH  /api/care-logs/{log_id}
DELETE /api/care-logs/{log_id}
```

프론트는 수정 내용 또는 삭제 대상을 사용자에게 확인받은 뒤 호출합니다. **백엔드 확정 필요:** 수정 요청 body의 정확한 구조.

### 패턴 조회

```http
GET /api/care-patterns/{baby_id}?days=7
```

- `days`: 1~30, 기본 7
- 충분 기준: 유효 기록 5건 이상이고 기록일 3일 이상
- `sufficient_data=false`이면 평균을 지어내지 않고 부족 안내를 표시합니다.
- 계산 불가 평균은 `0`이 아니라 `null`입니다.

---

## 5. 성장·알림·예방접종

### 성장

```http
GET /api/growth/{baby_id}
```

성장 기록과 월령·성별 참고값을 함께 표시합니다. 프론트는 정상·비정상·진단 표현을 사용하지 않습니다.

### 수유 알림

```http
GET   /api/reminders/feeding/{baby_id}
PATCH /api/reminders/{reminder_id}
```

알림 상태 변경 요청의 확정 action:

```json
{"action": "confirm"}
```

```json
{"action": "snooze"}
```

```json
{"action": "skip"}
```

| action | UI 의미 |
| --- | --- |
| `confirm` | 알림 확인 상태 변경 |
| `snooze` | 기록 없이 현재 시각부터 10분 뒤 다시 알림 |
| `skip` | 기록 없이 설정 간격 뒤 다시 알림 |

수유했어요 버튼은 `confirm`만으로 기록을 만들지 않습니다. 수유 기록을 별도로 저장해야 다음 알림 기준이 갱신됩니다.

**백엔드 확정 필요:** 수유 간격 설정 저장 API의 경로·요청·응답 구조.

### 예방접종

```http
GET /api/vaccinations/{baby_id}
```

프론트는 완료 이력과 다음 접종명·차수·예정일을 표시하고, 테스트용 목데이터임을 안내합니다.

---

## 6. 병원 검색과 기저귀 사진

### 병원 검색

```http
GET /api/hospitals/search
```

요청 파라미터:

```text
region=서울특별시 동작구
type=pediatric | emergency
page=1
limit=10
```

**백엔드 확정 필요:** 병원 종류 파라미터의 실제 이름(`type` 등). 문서상 `pediatric`/`emergency`에 따라 Tool을 선택하는 규칙만 확정되어 있습니다.

소아과 결과:

```json
{
  "hospital_name": "예시소아청소년과",
  "address": "서울특별시 동작구 예시로 1",
  "phone": "02-000-0000",
  "operating_hours": null
}
```

응급실 결과는 `operating_hours` 대신 `emergency_level`을 포함할 수 있습니다. `phone`, 운영시간, 응급 등급은 `null`일 수 있으므로 빈 문자열을 강제하지 않습니다. 결과 없음은 오류가 아니며 빈 목록으로 표시합니다.

### 기저귀 사진 분석

```http
POST /api/images/diaper-analysis
```

- 파일: 이미지 파일 업로드 방식(`multipart/form-data`)으로 예상됩니다.
- 지원 제한: 최대 10MB. **백엔드 확정 필요:** 허용 확장자 목록과 multipart 필드명.
- 프론트가 함께 제공해야 하는 맥락: `baby_id`, 월령, 수유 방식, 선택 정보인 발열 여부·최근 24시간 배변 횟수.

주요 결과 필드:

```json
{
  "is_analyzable": true,
  "quality_issues": [],
  "observation": {},
  "risk": {"level": "none", "signals": [], "recommended_action": ""},
  "follow_up_questions": [],
  "sources": [],
  "warnings": [],
  "safety_notice": "사진만으로 질환을 진단할 수 없습니다."
}
```

- `is_analyzable=false`은 서버 오류가 아니라 재촬영 안내 상태입니다.
- `risk.level`은 `none`, `attention`, `urgent`, `emergency` 중 하나입니다.
- 분석 결과를 배변 기록으로 저장할 때는 구조화된 관찰값을 배변 기록 폼에 채운 뒤, 사용자가 별도로 저장해야 합니다.

---

## 7. 채팅과 SSE

### 일반 채팅

```http
POST /api/chat
```

**백엔드 확정 필요:** request body의 실제 필드명. 프론트에서 필요한 정보는 최소 `message`, `baby_id`, `session_id`입니다.

채팅 응답 `response_type`:

```text
text
options
record_confirmation
hospital_list
diaper_analysis
stt_record_approval
speech_transcription
out_of_scope
unsupported_feature
clarification_required
policy_blocked
error
```

프론트는 `response_type`별 전용 카드로 렌더링하고, 일반 오류와 정책 차단·추가 질문·서비스 범위 밖 응답을 구분합니다.

### 스트리밍 채팅

```http
POST /api/chat/stream
```

SSE 진행 상태:

```text
received
loading_context
analyzing_request
using_tool
generating_answer
completed
error
```

- Tool 호출이 없는 질문은 `using_tool` 단계가 생략될 수 있습니다.
- `error` 이벤트를 받은 뒤 스트림을 종료합니다.
- 프론트는 내부 Prompt, Memory 원문, Stack Trace를 보여 주지 않습니다.

**백엔드 확정 필요:** SSE의 실제 event 이름, `data` JSON 구조, 최종 답변과 `response_type` 전달 방식.

---

## 8. STT 승인 계약

문서상 STT 처리 규칙은 확정되어 있으나, 업로드·승인 API 경로는 아직 명시되지 않았습니다.

확정 규칙:

1. MP3, WAV, M4A, WebM만 지원하고 최대 20MB입니다.
2. 음성은 텍스트로 변환한 뒤 일반 질문·실제 기록·미수유 표현으로 구분합니다.
3. 실제 기록에만 `stt_record_approval` 응답과 `tool_call_id`가 생성됩니다.
4. 사용자가 승인하면 백엔드는 Redis의 Snapshot을 검증하고 동일 기록을 한 번만 저장합니다.
5. 미수유 표현은 기록과 승인 Snapshot을 생성하지 않습니다.

**백엔드 확정 필요:**

| 필요한 API | 필요한 데이터 |
| --- | --- |
| 음성 업로드·STT | 파일, `baby_id`, `session_id` |
| STT 승인 | `tool_call_id`, `baby_id`, `session_id`, `request_id` |
| STT 거절 | `tool_call_id`, `baby_id`, `session_id`, `request_id` |

프론트는 승인 요청에서 기록 내용·수유량을 다시 수정해 신뢰 가능한 값으로 보내지 않습니다. 사용자에게 보인 Snapshot과 `tool_call_id`로 승인만 요청합니다.

---

## 9. `api.py` 구현 체크리스트

- 모든 HTTP 호출은 timeout과 예외 처리를 적용합니다.
- 공통 응답을 하나의 형식으로 파싱합니다.
- 비정상 응답에서도 `message`, `request_id`, 오류 코드를 안전하게 읽습니다.
- 파일 업로드는 MIME 타입과 크기를 프론트에서도 먼저 검사합니다.
- 저장 요청은 버튼을 잠그고 `idempotency_key`를 재사용합니다.
- 성공한 저장·수정·삭제 뒤에는 해당 목록과 홈 요약을 다시 조회합니다.
- 문서에서 **백엔드 확정 필요**로 표시한 항목은 임의로 구현하지 않고 담당자와 확정한 뒤 반영합니다.
