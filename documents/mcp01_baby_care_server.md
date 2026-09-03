# baby_care_server 최종 개발계획서

> 0~36개월 영유아의 육아 기록 저장·조회·패턴 계산과 기저귀 변 사진 분석을 담당하는 Python MCP 서버

## 1. 서버 책임

### 담당

- 수유·수면·기저귀·성장 기록 저장
- 오늘·기간별 육아 기록 조회
- 최근 7일 생활 패턴 계산
- 기저귀 변 사진 품질 검사와 관찰
- 규칙 기반 위험 신호 확인
- `stool` 카테고리 RAG 검색
- 근거와 안전 안내가 포함된 변 사진 분석 결과 반환

### 담당하지 않음

- 가짜 로그인과 아기 정보 등록·수정
- STT 음성→텍스트 변환
- 수유 알림 시간 계산과 상태 관리
- 기록 수정·삭제 API
- 예방접종 데이터 제공
- 소아과·응급실 검색
- 질병 확정 진단

위 기능은 FastAPI 백엔드 또는 `baby_info_server`가 담당합니다.

## 2. 기술 구성

| 영역 | 기술 |
|---|---|
| 언어 | Python |
| MCP | MCP Python SDK·FastMCP |
| Transport | Streamable HTTP |
| DB | PostgreSQL |
| 데이터 검증 | Pydantic `Field` |
| Vision | OpenAI Responses API |
| 임베딩 | Ollama Embedding |
| RAG | PostgreSQL·pgvector |
| 테스트 | pytest |

기본 Endpoint:

```text
/mcp
```

## 3. MCP Tool 목록

Tool은 MCP 계획서 기준 3개로 유지합니다.

| Tool | 역할 | DB 변경 | 승인 |
|---|---|---:|---|
| `record_care_event` | 육아 기록 1건 저장 | O | 사용자 최종 확인 필요 |
| `get_care_records` | 기록·패턴 조회 | X | 자동 실행 |
| `analyze_infant_stool` | 기저귀 변 사진 Workflow 분석 | X | 사진 업로드 후 실행 |

### 3.1 `record_care_event`

`event_type`은 다음 값만 허용합니다.

```text
feeding
sleep
diaper
growth
```

공통 입력:

```json
{
  "baby_id": "baby-001",
  "event_type": "feeding",
  "recorded_at": "2026-09-03T14:30:00+09:00",
  "idempotency_key": "session-001-tool-001",
  "confirmed_by_user": true,
  "feeding_type": "formula",
  "amount_ml": 100
}
```

검증 규칙:

- `baby_id` 필수
- `event_type`은 약속된 문자열만 허용
- `confirmed_by_user=true`일 때만 저장
- `idempotency_key` 중복 저장 금지
- `recorded_at`이 없으면 한국 시간 기준 현재 시각 사용

종류별 입력 예시:

```json
{"event_type":"sleep","action":"start"}
```

```json
{"event_type":"diaper","urine":true,"stool":false}
```

```json
{
  "event_type":"growth",
  "weight_kg":7.2,
  "height_cm":66.0,
  "head_circumference_cm":42.0
}
```

### 3.2 `get_care_records`

`query_type`은 다음 값만 허용합니다.

```text
today
range
pattern
latest_feeding
```

입력 예시:

```json
{
  "baby_id": "baby-001",
  "query_type": "pattern",
  "days": 7
}
```

반환 항목:

- 수유 횟수·평균 수유량·평균 수유 간격
- 총 수면 시간·평균 수면 시간
- 소변·대변 횟수
- 기록 부족 여부 `sufficient_data`

### 3.3 `analyze_infant_stool`

입력 예시:

```json
{
  "baby_id": "baby-001",
  "image_path": "temporary/uuid-image.jpg",
  "baby_age_months": 3,
  "feeding_type": "formula",
  "has_fever": null,
  "stool_count_24h": null
}
```

처리 순서:

```text
이미지 형식·크기 검사
→ 이미지 품질 검사
→ Vision 관찰
→ 규칙 기반 위험 신호 확인
→ 필요 시 추가 질문 반환
→ 공용 RAG에서 category=stool 검색
→ 관찰 결과·출처·안전 안내 반환
→ 임시 이미지 삭제
```

이 Tool은 정해진 순서로 실행되는 Workflow Tool이며 별도의 자율 Agent가 아닙니다.

## 4. 육아 기록 로직

### 수유

- `feeding_type`: `breast`, `formula`, `mixed`
- `amount_ml`은 입력된 경우 0보다 커야 함
- 확정된 기록만 저장

### 수면

- `action`: `start`, `end`
- 이미 수면 중인데 다시 시작하면 거부
- 시작 기록 없이 종료하면 거부

### 기저귀

- `urine`, `stool` 중 하나 이상은 `true`

### 성장

- 키·몸무게·머리둘레 중 하나 이상 입력
- 입력값은 0보다 커야 함
- 정상·비정상을 판단하지 않음

## 5. DB 책임

`baby_care_server`는 공용 PostgreSQL의 `care_logs` 테이블에 기록을 저장·조회합니다.

```text
care_logs
├─ id
├─ baby_id
├─ log_type
├─ recorded_at
├─ details JSONB
├─ idempotency_key
├─ created_at
└─ updated_at
```

개별 `feeding_logs`, `sleep_logs`, `diaper_logs`, `growth_logs` 테이블은 만들지 않습니다.

인덱스:

```text
(baby_id, recorded_at DESC)
(baby_id, log_type)
```

기저귀 사진 원본과 분석 결과는 DB에 영구 저장하지 않습니다. 보호자가 배변 기록 저장을 승인하면 관찰한 색상·형태만 `care_logs.details`에 저장할 수 있습니다.

### 5.1 STT 육아 기록 연동

STT는 FastAPI 백엔드가 담당하며 `baby_care_server`는 음성 파일을 직접 처리하지 않습니다. `baby_care_server`는 STT로 변환된 내용 중 사용자가 최종 승인한 육아 기록만 전달받아 저장합니다.

전체 처리 흐름:

```text
보호자 음성 업로드
→ FastAPI에서 음성 파일 형식·크기 검증
→ FastAPI가 STT API 호출
→ 변환된 텍스트를 AI Agent에 전달
→ Agent가 육아 기록 의도와 필드 추출
→ FastAPI가 사용자에게 기록 내용 확인 요청
→ 승인 전 데이터를 Redis에 임시 저장
→ 사용자 승인
→ FastAPI MCP Client가 record_care_event 호출
→ baby_care_server가 입력값 검증
→ care_log_repository가 care_logs에 저장
→ 저장 결과를 FastAPI에 반환
```

예를 들어 STT 결과가 다음과 같아도 바로 저장하지 않습니다.

```text
서아가 방금 분유를 100ml 먹었어.
```

AI Agent는 먼저 확인용 응답을 생성합니다.

```json
{
  "response_type": "record_confirmation",
  "message": "서아가 현재 시간에 분유 100ml를 먹은 것으로 기록할까요?",
  "tool_call_id": "tool-call-001",
  "options": [
    {
      "label": "기록 완료",
      "action": "approve"
    },
    {
      "label": "수정하기",
      "action": "edit"
    }
  ]
}
```

승인 전 데이터는 FastAPI가 Redis에 임시 저장합니다.

```text
tool_approval:{tool_call_id}
```

```json
{
  "tool_name": "record_care_event",
  "status": "pending",
  "baby_id": "baby-001",
  "arguments": {
    "event_type": "feeding",
    "feeding_type": "formula",
    "amount_ml": 100,
    "recorded_at": "2026-09-03T14:30:00+09:00"
  }
}
```

사용자가 `기록 완료`를 선택하면 FastAPI의 MCP Client가 다음 입력으로 Tool을 호출합니다.

```json
{
  "baby_id": "baby-001",
  "event_type": "feeding",
  "feeding_type": "formula",
  "amount_ml": 100,
  "recorded_at": "2026-09-03T14:30:00+09:00",
  "idempotency_key": "session-001-tool-call-001",
  "confirmed_by_user": true
}
```

`baby_care_server` 내부 처리:

```text
record_care_event
→ Pydantic 입력 검증
→ confirmed_by_user 확인
→ idempotency_key 중복 확인
→ care_service
→ care_log_repository
→ PostgreSQL care_logs 저장
```

저장이 완료되면 다음과 같은 결과를 FastAPI에 반환합니다.

```json
{
  "success": true,
  "message": "분유 100ml를 기록했습니다.",
  "data": {
    "log_id": "log-001",
    "event_type": "feeding",
    "recorded_at": "2026-09-03T14:30:00+09:00"
  }
}
```

중요 원칙:

- STT 결과만으로 기록을 자동 저장하지 않음
- 사용자가 `기록 완료`를 선택해야 함
- 승인 전 데이터는 DB가 아니라 Redis에 저장
- 승인 후 `record_care_event`가 `care_logs`에 영구 저장
- 동일한 승인 요청의 중복 저장은 `idempotency_key`로 방지
- STT 음성 원본은 `baby_care_server`에 전달하지 않음

## 6. 공용 RAG 사용

RAG 테이블은 `baby_info_server`가 색인·관리합니다.

```text
documents
document_chunks
```

`baby_care_server`는 기저귀 변 분석 시 `category=stool` 자료만 읽습니다.

- 임베딩 생성: Ollama Embedding
- 벡터 저장·검색: PostgreSQL·pgvector
- 문서와 사용자 질문은 동일한 Ollama 임베딩 모델 사용
- 답변 생성: OpenAI Responses API
- 벡터 차원은 두 MCP 서버에서 동일하게 설정
- 문서 등록과 재색인은 `baby_info_server` 담당

## 7. 알림 연동

수유 알림은 FastAPI 백엔드가 계산합니다. `baby_care_server`는 `get_care_records(query_type="latest_feeding")`으로 마지막 확정 수유 기록을 반환합니다.

```text
FastAPI
→ 마지막 수유 조회
→ reminder_settings 조회
→ 다음 알림 시간 계산
```

`건너뛰기`와 `10분 후` 상태는 Redis에 저장하며 MCP 서버는 알림 상태를 변경하지 않습니다.

## 8. 디렉터리 구조

```text
baby_care_server/
├─ server.py
├─ config.py
├─ constants.py
├─ tools/
│  ├─ record_care_event.py
│  ├─ get_care_records.py
│  └─ analyze_infant_stool.py
├─ schemas/
│  ├─ care.py
│  └─ stool.py
├─ services/
│  ├─ care_service.py
│  ├─ pattern_service.py
│  └─ stool_analysis_service.py
├─ repositories/
│  ├─ care_log_repository.py
│  └─ rag_repository.py
├─ workflows/
│  └─ stool_analysis_workflow.py
├─ rules/
│  └─ infant_stool_triage.yaml
├─ prompts/
│  ├─ stool_vision_prompt.txt
│  └─ stool_answer_prompt.txt
└─ tests/
   ├─ test_record_care_event.py
   ├─ test_get_care_records.py
   └─ test_stool_analysis.py
```

## 9. 환경변수

```text
POSTGRES_DSN=postgresql+psycopg://postgres:password@localhost:5432/baby_ai

OPENAI_API_KEY=
OPENAI_VISION_MODEL=
OPENAI_RESPONSE_MODEL=

OLLAMA_BASE_URL=
OLLAMA_EMBEDDING_MODEL=
OLLAMA_TIMEOUT_SECONDS=30
EMBEDDING_DIMENSIONS=

IMAGE_MAX_BYTES=10485760
APP_TIMEZONE=Asia/Seoul

MCP_HOST=127.0.0.1
MCP_PORT=8101
MCP_STREAMABLE_HTTP_PATH=/mcp
```

## 10. 안전·오류 처리

- 진단·처방을 제공하지 않음
- 사진에서 직접 관찰 가능한 특징과 위험 신호만 설명
- 위험 신호가 있으면 의료기관·119 안내 우선
- 사진 원본·API Key·DB 접속정보를 로그에 남기지 않음
- Vision·RAG 실패를 구분해 반환
- RAG 근거가 부족하면 추측하지 않음
- 중복 `idempotency_key`는 기존 결과 반환

## 11. 필수 테스트

- 허용되지 않은 `event_type`
- 사용자 승인 없는 기록 저장
- 중복 기록 요청
- 수면 중복 시작·시작 없는 종료
- 기저귀 `urine=false`, `stool=false`
- 성장값이 모두 없는 경우
- 잘못된 이미지 형식·용량 초과
- 이미지 품질 부족
- RAG 결과 없음
- Vision API 실패
- `stool` 이외 카테고리 접근 차단

## 12. 완료 기준

- MCP Tool은 3개만 등록
- 모든 육아 기록은 `care_logs`에 저장
- `record_care_event`는 사용자 승인 후 실행
- STT 기록은 FastAPI에서 변환·승인한 뒤 `record_care_event`로 전달
- `get_care_records`가 기록과 패턴을 반환
- `analyze_infant_stool`이 고정 Workflow로 실행
- RAG는 공용 테이블과 Ollama 임베딩 사용
- STT·알림·예방접종·병원 검색은 담당하지 않음
