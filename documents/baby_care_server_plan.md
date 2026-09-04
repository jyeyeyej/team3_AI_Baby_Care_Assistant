# baby_care_server 최종 개발계획서

> 0~36개월 영유아의 육아 기록 저장·조회·패턴 계산과 기저귀 변 사진 분석을 담당하는 Python MCP 서버
> 

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

---

## 2. 기술 구성

| 영역 | 기술 |
| --- | --- |
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

```
/mcp
```

---

## 3. MCP Tool 목록

Tool은 MCP 계획서 기준 3개로 유지합니다.

| Tool | 역할 | DB 변경 | 승인 |
| --- | --- | --- | --- |
| `record_care_event` | 육아 기록 1건 저장 | O | STT 입력만 사용자 최종 확인 필요 |
| `get_care_records` | 기록·패턴 조회 | X | 자동 실행 |
| `analyze_infant_stool` | 기저귀 변 사진 Workflow 분석 | X | 사진 업로드 후 실행 |

### 3.1 `record_care_event`

`event_type`은 다음 값만 허용합니다.

```
feeding
sleep
diaper
growth
```

`input_source`는 기록 입력 경로를 나타내며 다음 값만 허용합니다.

```
text
ui
stt
```

- `text`: 채팅 자연어 입력
- `ui`: 버튼·숫자 UI 입력
- `stt`: 음성을 STT로 변환한 입력

공통 입력:

```json
{
  "baby_id": "baby-001",
  "event_type": "feeding",
  "input_source": "ui",
  "recorded_at": "2026-09-03T14:30:00+09:00",
  "idempotency_key": "session-001-tool-001",
  "feeding_type": "formula",
  "amount_ml": 100
}
```

검증 규칙:

- `baby_id` 필수
- `event_type`은 약속된 문자열만 허용
- `input_source`는 필수이며 `text`, `ui`, `stt` 중 하나만 허용
- `confirmed_by_user`는 STT 입력에서만 승인 여부 확인에 사용
- `input_source="text"` 또는 `input_source="ui"`이면 별도 승인 없이 저장
- `input_source="stt"`이면 `confirmed_by_user=true`일 때만 저장
- STT 입력인데 `confirmed_by_user`가 없거나 `false`이면 저장 거부
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

```
today
range
pattern
latest_feeding
```

`pattern` 입력 예시:

```json
{
  "baby_id": "baby-001",
  "query_type": "pattern",
  "days": 7
}
```

`range`는 한국 날짜 기준으로 시작일과 종료일을 모두 포함합니다.

```json
{
  "baby_id": "baby-001",
  "query_type": "range",
  "start_date": "2026-09-01",
  "end_date": "2026-09-04"
}
```

조회 성공 응답은 모든 `query_type`에서 같은 상위 구조를 사용합니다.

```json
{
  "success": true,
  "message": "육아 기록을 조회했습니다.",
  "data": {
    "baby_id": "baby-001",
    "query_type": "today",
    "records": [],
    "pattern": null,
    "latest_feeding": null
  },
  "error": null
}
```

- `today`, `range`: `records`에 기록 목록을 반환
- `pattern`: `pattern`에 계산 결과를 반환
- `latest_feeding`: `latest_feeding`에 마지막 수유 기록을 반환
- 해당 기록이 없으면 오류가 아니라 `records=[]` 또는 `latest_feeding=null` 반환
- DB 컬럼명은 `log_type`, MCP 요청·응답 필드명은 `event_type`으로 사용

기록 한 건의 구조:

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

`pattern` 반환 구조:

```json
{
  "period_days": 7,
  "start_date": "2026-08-29",
  "end_date": "2026-09-04",
  "record_count": 35,
  "recorded_day_count": 6,
  "sufficient_data": true,
  "insufficient_reason": null,
  "feeding": {
    "count": 15,
    "average_amount_ml": 105.5,
    "average_interval_minutes": 182.0
  },
  "sleep": {
    "completed_session_count": 7,
    "total_sleep_minutes": 980,
    "average_sleep_minutes": 140.0
  },
  "diaper": {
    "urine_count": 10,
    "stool_count": 3
  }
}
```

패턴 반환 항목:

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

```
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

정상 분석 성공 응답:

```json
{
  "success": true,
  "message": "기저귀 사진에서 관찰 가능한 특징을 정리했습니다.",
  "data": {
    "baby_id": "baby-001",
    "is_analyzable": true,
    "quality_issues": [],
    "observation": {
      "color": "yellow",
      "consistency": "loose",
      "visible_red_area": false,
      "black_tarry_appearance": false,
      "pale_or_white_appearance": false,
      "uncertainty": "medium",
      "notes": ["사진의 조명에 따라 실제 색상과 다르게 보일 수 있습니다."]
    },
    "risk": {
      "level": "none",
      "signals": [],
      "recommended_action": "아기의 상태와 다음 배변을 함께 관찰해 주세요."
    },
    "follow_up_questions": [],
    "sources": [
      {
        "document_id": "doc-001",
        "title": "영아 배변 관찰 안내",
        "organization": "공식 제공기관",
        "source_url": "https://example.org/document",
        "score": 0.87
      }
    ],
    "warnings": [],
    "safety_notice": "사진만으로 질환을 진단할 수 없습니다."
  },
  "error": null
}
```

이미지 품질 부족은 서버 오류가 아니므로 `success=true`, `is_analyzable=false`로 반환합니다.

```json
{
  "success": true,
  "message": "사진이 흐려서 충분히 관찰하기 어렵습니다.",
  "data": {
    "baby_id": "baby-001",
    "is_analyzable": false,
    "quality_issues": ["사진이 흐립니다."],
    "observation": null,
    "risk": null,
    "follow_up_questions": ["밝은 곳에서 기저귀 전체가 보이도록 다시 촬영해 주세요."],
    "sources": [],
    "warnings": [],
    "safety_notice": "사진만으로 질환을 진단할 수 없습니다."
  },
  "error": null
}
```

RAG 검색 결과가 없는 것은 오류가 아니며 `sources=[]`로 반환합니다. Vision은 성공했지만 RAG만 실패한 경우에도 관찰 결과는 반환하고 `warnings`에 `RAG_SERVICE_ERROR`를 추가합니다.

위험 수준 `risk.level`은 다음 값만 사용합니다.

```
none
attention
urgent
emergency
```

`none`은 정상 판정이 아니라 정해진 규칙에 해당하는 위험 신호가 관찰되지 않았다는 의미입니다.

---

## 4. 육아 기록 로직

### 수유

- `feeding_type`: `breast`, `formula`, `mixed`
- `amount_ml`은 입력된 경우 0 이상이어야 함
- 텍스트·UI 기록은 즉시 저장하고 STT 기록은 승인된 경우에만 저장

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

### 패턴 데이터 충분 기준

`pattern` 조회의 `days`는 기본값 7이며 1~30 범위만 허용합니다.

다음 조건을 모두 만족하면 `sufficient_data=true`로 반환합니다.

- 조회 기간의 전체 유효 기록이 5건 이상
- 기록이 존재하는 서로 다른 날짜가 3일 이상

조건을 만족하지 않으면 `sufficient_data=false`와 `insufficient_reason`을 반환합니다. 데이터가 부족해도 계산 가능한 값은 반환하지만 계산할 수 없는 평균은 `0`이 아니라 `null`로 반환합니다.

- 평균 수유량: `amount_ml`이 있는 수유 기록만 계산
- 평균 수유 간격: 수유 기록이 2건 이상일 때만 계산
- 수면 시간: 정상적으로 연결된 `start`, `end`만 계산
- 짝이 없는 수면 기록: 수면 평균 계산에서 제외
- 소변·대변 횟수: 각각 `true`인 기록 수 계산

---

## 5. DB 책임

`baby_care_server`는 개발 단계에서는 담당자 컴퓨터의 Docker PostgreSQL을 사용하고, 최종 통합 단계에서는 팀 공용 PostgreSQL의 `care_logs` 테이블에 기록을 저장·조회합니다.

```
care_logs
├─ id VARCHAR(100) PRIMARY KEY
├─ baby_id VARCHAR(100) NOT NULL
├─ log_type VARCHAR(20) NOT NULL
├─ recorded_at TIMESTAMPTZ NOT NULL
├─ details JSONB NOT NULL
├─ idempotency_key VARCHAR(100) NOT NULL UNIQUE
├─ created_at TIMESTAMPTZ NOT NULL
└─ updated_at TIMESTAMPTZ NOT NULL
```

### 5.1 DB 컬럼 통일 규칙

- ID 관련 컬럼은 `VARCHAR(100)`으로 통일
- Backend의 `babies.id`와 Care의 `care_logs.baby_id`는 같은 값과 자료형 사용
- Backend와 Care가 함께 사용하는 `care_logs` 컬럼 구조는 동일하게 유지
- Info의 `documents.id`와 `document_chunks.document_id`는 같은 자료형 사용
- RAG `category`는 `documents`에 저장
- Care Server는 `documents.category='stool'`인 문서에 연결된 Chunk만 조회
- 날짜·시간 컬럼은 `TIMESTAMPTZ` 사용

`care_logs.baby_id`는 최종 통합 DB에서 `babies.id`를 참조합니다. 로컬 개발 DB에서 외래키까지 적용해 테스트하려면 Backend가 제공한 `babies` 스키마 또는 최소 테스트용 `babies(id VARCHAR(100) PRIMARY KEY)` 테이블과 테스트 아기 데이터를 먼저 준비합니다. Care 담당자는 `babies` 기능을 구현하지 않고 `care_logs`만 관리합니다.

### 5.2 개발·통합 순서

개발 단계:

```text
각 담당자가 자기 컴퓨터의 Docker PostgreSQL 사용
→ Backend: babies, reminder_settings, user_memories 구현·테스트
→ Care: care_logs 구현·테스트
→ Info: documents, document_chunks 구현·테스트
→ 각자 자기 서버 기능 테스트
```

Care Server의 로컬 테스트에서는 Backend의 테스트용 `baby_id`와 동일한 `VARCHAR(100)` 값을 사용합니다. `stool` RAG는 Info Server의 테이블이 준비되기 전까지 Repository를 Mock으로 테스트할 수 있습니다.

각자 기능 구현 성공 후:

```text
baby_id와 document_id 자료형 확인
→ care_logs 컬럼·details JSON 구조 확인
→ TIMESTAMPTZ와 시간대 처리 확인
→ MCP Tool 입력·출력 Schema 확인
```

최종 통합 테스트 직전에는 한 컴퓨터의 Docker PostgreSQL에 다음 6개 테이블을 모두 생성합니다.

```text
babies
care_logs
reminder_settings
documents
document_chunks
user_memories
```

통합 DB에서는 테이블을 중복 생성하지 않고, 팀에서 합의한 하나의 스키마를 사용합니다.

6개 테이블을 생성한 뒤 Backend, Care Server, Info Server를 모두 해당 PostgreSQL 하나에 연결합니다.

```text
Backend ───────┐
Care Server ───┼──→ 통합 PostgreSQL 1개
Info Server ───┘
```

마지막으로 다음 기능을 전체 프로젝트에서 통합 테스트합니다.

- 아기 등록
- 육아 기록 저장·조회
- 사용자 Memory
- RAG 검색
- 기저귀 변 분석
- Backend와 두 MCP Server의 연동

정리하면 개발 중에는 각 담당자가 자기 서버와 담당 DB 테이블을 로컬 Docker에서 구현·테스트하고, 기능 완성 후에는 한 컴퓨터의 PostgreSQL에 6개 테이블을 구성하여 세 서버를 함께 연결합니다.

개별 `feeding_logs`, `sleep_logs`, `diaper_logs`, `growth_logs` 테이블은 만들지 않습니다.

인덱스:

```
(baby_id, recorded_at DESC)
(baby_id, log_type)
```

기저귀 사진 원본과 분석 결과는 DB에 영구 저장하지 않습니다.

보호자가 배변 기록 저장을 승인하면 관찰한 색상·형태만 `care_logs.details`에 저장할 수 있습니다.

### 5.3 입력 경로별 육아 기록 연동

`record_care_event`는 `input_source`에 따라 승인 정책을 구분합니다.

텍스트 입력:

```
사용자 텍스트
→ FastAPI / Agent가 기록 의도와 필드 추출
→ record_care_event(input_source="text")
→ 별도 승인 없이 즉시 저장
```

UI 입력:

```
Frontend UI
→ FastAPI
→ record_care_event(input_source="ui")
→ 별도 승인 없이 즉시 저장
```

STT 입력:

```
보호자 음성
→ FastAPI에서 STT 처리
→ 사용자 최종 확인
→ record_care_event(input_source="stt", confirmed_by_user=true)
→ 저장
```

### 5.4 STT 육아 기록 연동

STT는 FastAPI 백엔드가 담당하며 `baby_care_server`는 음성 파일을 직접 처리하지 않습니다.

`baby_care_server`는 STT로 변환된 내용 중 사용자가 최종 승인한 육아 기록만 전달받아 저장합니다.

전체 처리 흐름:

```
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

```
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

승인 전 데이터는 FastAPI가 Redis에 임시 저장합니다. 이 Redis 값은 `baby_care_server`가 직접 관리하지 않습니다.

```
stt_approval:{tool_call_id}
```

```json
{
  "tool_name": "record_care_event",
  "status": "pending",
  "baby_id": "baby-001",
  "arguments": {
    "event_type": "feeding",
    "input_source": "stt",
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
  "input_source": "stt",
  "feeding_type": "formula",
  "amount_ml": 100,
  "recorded_at": "2026-09-03T14:30:00+09:00",
  "idempotency_key": "session-001-tool-call-001",
  "confirmed_by_user": true
}
```

`baby_care_server` 내부 처리:

```
record_care_event
→ Pydantic 입력 검증
→ input_source 확인
→ STT 입력인 경우 confirmed_by_user=true 확인
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
    "recorded_at": "2026-09-03T14:30:00+09:00",
    "duplicated": false
  },
  "error": null
}
```

중요 원칙:

- 텍스트와 UI 기록은 별도 승인 없이 저장
- STT 결과만으로 기록을 자동 저장하지 않음
- STT 기록은 사용자가 `기록 완료`를 선택해야 함
- STT 승인 전 데이터는 DB가 아니라 FastAPI가 관리하는 Redis에 저장
- STT 승인 후 `record_care_event`가 `care_logs`에 영구 저장
- 동일한 승인 요청의 중복 저장은 `idempotency_key`로 방지
- STT 음성 원본은 `baby_care_server`에 전달하지 않음

---

## 6. 공용 RAG 사용

RAG 테이블은 `baby_info_server`가 색인·관리합니다.

```
documents
document_chunks
```

`baby_care_server`는 기저귀 변 분석 시 `category=stool` 자료만 읽습니다.

- **검색 Query 임베딩 생성: Ollama Embedding**
- **벡터 검색: PostgreSQL·pgvector**
- 문서와 검색 Query는 동일한 Ollama 임베딩 모델 사용
- 답변 생성: OpenAI Responses API
- 벡터 차원은 두 MCP 서버에서 동일하게 설정
- 문서 등록과 재색인은 `baby_info_server` 담당

---

## 7. 알림 연동

수유 알림은 FastAPI 백엔드가 계산합니다.

`baby_care_server`는 `get_care_records(query_type="latest_feeding")`으로 마지막 확정 수유 기록을 반환합니다.

```
FastAPI
→ 마지막 수유 조회
→ reminder_settings 조회
→ 다음 알림 시간 계산
```

`건너뛰기`와 `10분 후` 상태는 Redis에 저장하며 MCP 서버는 알림 상태를 변경하지 않습니다.

---

## 8. 디렉터리 구조

```

baby_care_server/
├─ server.py
├─ config.py
├─ constants.py
│
├─ tools/
│  ├─ record_care_event.py
│  ├─ get_care_records.py
│  └─ analyze_infant_stool.py
│
├─ schemas/
│  ├─ care.py
│  └─ stool.py
│
├─ services/
│  ├─ care_service.py
│  ├─ pattern_service.py
│  └─ stool_analysis_service.py
│
├─ repositories/
│  ├─ care_log_repository.py
│  └─ rag_repository.py
│
├─ prompts/
│  ├─ stool_vision_prompt.txt
│  └─ stool_answer_prompt.txt
│
├─ workflows/
│  └─ stool_analysis_workflow.py
│
├─ rules/
│  └─ infant_stool_triage.yaml
│
└─ tests/
   ├─ test_record_care_event.py
   ├─ test_get_care_records.py
   └─ test_stool_analysis.py
```

```

---

## 9. 환경변수

```
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

---

## 10. 안전·오류 처리

- 진단·처방을 제공하지 않음
- 사진에서 직접 관찰 가능한 특징과 위험 신호만 설명
- 위험 신호가 있으면 의료기관·119 안내 우선
- 사진 원본·API Key·DB 접속정보를 로그에 남기지 않음
- Vision·RAG 실패를 구분해 반환
- RAG 근거가 부족하면 추측하지 않음
- 중복 `idempotency_key`는 기존 결과 반환

### 10.1 Tool 공통 응답 구조

세 Tool은 `success`, `message`, `data`, `error` 필드를 공통으로 사용합니다.

성공:

```json
{
  "success": true,
  "message": "요청을 처리했습니다.",
  "data": {},
  "error": null
}
```

업무 오류:

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

Pydantic 입력 검증 실패는 Tool 함수 실행 전 MCP 입력 검증 오류로 처리할 수 있습니다. DB 연결 자체 실패처럼 정상 흐름으로 복구하기 어려운 서버 장애는 예외로 처리합니다.

### 10.2 업무 오류 코드

| 오류 코드 | 발생 상황 |
| --- | --- |
| `BABY_NOT_FOUND` | 존재하지 않는 `baby_id` |
| `INVALID_DATE_RANGE` | 조회 시작일이 종료일보다 늦음 |
| `STT_CONFIRMATION_REQUIRED` | 승인되지 않은 STT 저장 요청 |
| `INVALID_CARE_EVENT` | 기록 종류별 필수값 오류 |
| `SLEEP_ALREADY_STARTED` | 진행 중인 수면이 있는데 다시 시작 |
| `SLEEP_START_NOT_FOUND` | 시작 기록 없이 수면 종료 |
| `IMAGE_NOT_FOUND` | 임시 이미지 파일 없음 |
| `INVALID_IMAGE_PATH` | 허용된 임시 폴더 밖의 경로 |
| `UNSUPPORTED_IMAGE_TYPE` | 허용하지 않는 이미지 형식 |
| `IMAGE_TOO_LARGE` | 이미지가 최대 크기 초과 |
| `VISION_API_ERROR` | Vision API 호출 실패 |
| `RAG_SERVICE_ERROR` | Ollama 또는 pgvector 조회 실패 |

동일한 `idempotency_key`가 이미 저장된 경우는 오류로 처리하지 않고 기존 성공 결과와 `duplicated=true`를 반환합니다. 새 기록은 `duplicated=false`를 반환합니다.

Vision 분석은 성공했지만 RAG만 실패한 경우 전체 실패로 처리하지 않습니다. 관찰 결과는 정상 반환하고 `data.warnings`에 다음 값을 추가합니다.

```json
{
  "code": "RAG_SERVICE_ERROR",
  "detail": "육아 참고자료를 조회하지 못했습니다."
}
```

---

## 11. 필수 테스트

- 허용되지 않은 `event_type`
- 허용되지 않은 `input_source`
- `amount_ml=0`인 수유 기록이 정상 저장되는지 확인
- `amount_ml`이 음수인 경우 저장 거부
- `input_source="text"` 기록이 별도 승인 없이 저장되는지 확인
- `input_source="ui"` 기록이 별도 승인 없이 저장되는지 확인
- `input_source="stt"`인데 `confirmed_by_user`가 없거나 `false`인 경우 저장 거부
- `input_source="stt"`이고 `confirmed_by_user=true`인 경우 저장 성공
- 중복 기록 요청
- 중복 요청 시 기존 결과와 `duplicated=true` 반환
- 수면 중복 시작·시작 없는 종료
- 기저귀 `urine=false`, `stool=false`
- 성장값이 모두 없는 경우
- 잘못된 이미지 형식·용량 초과
- 이미지 품질 부족
- 이미지 품질 부족 시 `success=true`, `is_analyzable=false` 반환
- RAG 결과 없음
- Vision 성공·RAG 실패 시 관찰 결과와 `warnings` 반환
- Vision API 실패
- `stool` 이외 카테고리 접근 차단
- `range` 시작일이 종료일보다 늦은 경우
- `today`, `range` 기록 없음이 빈 배열로 반환되는지 확인
- 마지막 수유 기록 없음이 `latest_feeding=null`로 반환되는지 확인
- 기록 5건 이상·기록일 3일 이상이면 `sufficient_data=true`
- 데이터가 부족하거나 계산 불가능한 평균이 `null`로 반환되는지 확인
- 세 Tool의 응답이 공통 `success`, `message`, `data`, `error` 구조를 따르는지 확인

---

## 12. 완료 기준

- MCP Tool은 3개만 등록
- 개발 단계에서 Care 담당자의 Docker PostgreSQL로 `care_logs` 저장·조회 테스트 완료
- ID 관련 컬럼은 `VARCHAR(100)`, 날짜·시간 컬럼은 `TIMESTAMPTZ` 사용
- `care_logs.baby_id`는 Backend의 `babies.id`와 같은 값·자료형 사용
- 최종 통합 DB의 합의된 6개 테이블과 외래키 연결 확인
- Backend, Care Server, Info Server가 동일한 통합 PostgreSQL에 연결되는지 확인
- 아기 등록·육아 기록·Memory·RAG·변 분석의 전체 통합 테스트 완료
- 모든 육아 기록은 `care_logs`에 저장
- `record_care_event`는 텍스트·UI 입력을 별도 승인 없이 저장
- `record_care_event`는 STT 입력만 `confirmed_by_user=true`일 때 저장
- STT 기록은 FastAPI에서 변환·승인한 뒤 `record_care_event`로 전달
- `get_care_records`가 기록과 패턴을 반환
- `get_care_records`는 조회 유형과 관계없이 합의된 공통 Response Schema를 반환
- `analyze_infant_stool`이 고정 Workflow로 실행
- `analyze_infant_stool`은 분석 가능 여부·관찰·위험 수준·추가 질문·출처·경고·안전 안내를 구조화해 반환
- 예상 가능한 업무 오류는 공통 오류 Response Schema로 반환
- RAG는 공용 테이블과 Ollama 임베딩 사용
- STT·알림·예방접종·병원 검색은 담당하지 않음
