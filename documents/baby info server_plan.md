> 0~36개월 영유아 보호자를 위한 육아 지식 RAG와 지역명 기반 소아과·응급실 조회를 제공하는 Python MCP 서버
> 

## 1. 서버 책임

### 담당

- 수유·수면·이유식·발달·안전 육아 지식 RAG
- RAG 문서 색인과 임베딩 저장
- 공용 `documents`, `document_chunks` 관리
- 지역명 기반 실제 소아과 검색
- 지역명 기반 실제 응급실 검색
- 근거·출처·확인 시점이 포함된 답변 반환

### 담당하지 않음

- 로그인·인증·본인인증
- 아기 정보 등록·수정
- 육아 기록 저장·수정·삭제
- 수유 알림
- STT
- 기저귀 사진 분석
- 예방접종 조회
- 질병 진단·처방

예방접종은 FastAPI가 `vaccinations.json`을 조회합니다.

기저귀 사진은 `baby_care_server`의 `analyze_infant_stool`이 처리합니다.

---

## 2. 기술 구성

| 영역 | 기술 |
| --- | --- |
| 언어 | Python |
| MCP | MCP Python SDK·FastMCP |
| Transport | Streamable HTTP |
| DB | PostgreSQL |
| Vector DB | PostgreSQL·pgvector |
| 데이터 검증 | Pydantic `Field` |
| 임베딩 | Ollama Embedding |
| 답변 생성 | OpenAI Responses API |
| 공공데이터 | 소아과·응급의료기관 API |
| 테스트 | pytest |

기본 Endpoint:

```
/mcp
```

---

## 3. MCP Tool 목록

예방접종 Tool을 제외한 7개를 제공합니다.

### 의료기관 Tool

| Tool | 역할 |
| --- | --- |
| `search_pediatric_hospitals` | 지역명 기반 소아과 검색 |
| `search_emergency_hospitals` | 지역명 기반 응급실 검색 |

### 육아 지식 RAG Tool

| Tool | 고정 카테고리 | 검색 범위 |
| --- | --- | --- |
| `search_feeding_guide` | `feeding` | 모유·분유·수유량·수유 간격·트림 |
| `search_sleep_guide` | `sleep` | 월령별 수면·낮잠·수면 안전 |
| `search_weaning_guide` | `weaning` | 이유식 시기·단계·식재료·알레르기 주의 |
| `search_development_guide` | `development` | 신체·인지·언어·사회성 발달 |
| `search_safety_guide` | `safety` | 낙상·질식·화상·카시트 등 |

총 MCP Tool은 7개입니다.

---

## 4. 의료기관 Tool 명세

현재 위치·위도·경도·반경을 받지 않고 지역명을 직접 입력합니다.

### 공통 입력

```json
{
  "region": "서울특별시 동작구",
  "page": 1,
  "limit": 10
}
```

검증:

- `region`: 2~100자
- `page`: 1 이상
- `limit`: 1~30
- 빈 지역명 거부

삭제된 입력:

```
latitude
longitude
radius_km
```

### 소아과 출력

```json
{
  "success": true,
  "region": "서울특별시 동작구",
  "data": [
    {
      "hospital_name": "예시소아청소년과",
      "address": "서울특별시 동작구 예시로 1",
      "phone": "02-000-0000",
      "operating_hours": null
    }
  ],
  "source": "public_data",
  "checked_at": "2026-09-03T14:00:00+09:00",
  "notice": "운영시간과 진료 가능 여부는 방문 전 의료기관에 확인해 주세요."
}
```

### 응급실 출력

```json
{
  "success": true,
  "region": "서울특별시 동작구",
  "data": [
    {
      "hospital_name": "예시응급의료센터",
      "address": "서울특별시 동작구 예시로 2",
      "phone": "02-111-1111",
      "emergency_level": "regional"
    }
  ],
  "source": "public_data",
  "checked_at": "2026-09-03T14:00:00+09:00",
  "notice": "실시간 진료 가능 여부는 의료기관에 확인하고 위급한 경우 119에 연락하세요."
}
```

검색 결과가 없으면 오류가 아니라 빈 `data` 목록을 반환합니다.

### 의료기관 결과 필드 규칙

실제 공공데이터에서 일부 부가 정보가 누락될 수 있으므로 다음 규칙을 사용합니다.

| 구분 | 필수 필드 | `null` 허용 필드 |
| --- | --- | --- |
| 소아과 | `hospital_name`, `address` | `phone`, `operating_hours` |
| 응급실 | `hospital_name`, `address` | `phone`, `emergency_level` |

- `hospital_name` 또는 `address`가 없는 데이터는 결과 목록에서 제외합니다.
- 값이 없는 선택 정보는 빈 문자열 대신 `null`로 반환합니다.
- 소아과와 응급실 결과의 필드를 임의로 혼합하지 않습니다.

---

## 5. RAG Tool 명세

각 Tool은 검색 카테고리를 내부에서 고정합니다.

### 공통 입력

```json
{
  "query": "생후 3개월 아기의 일반적인 수유 간격은?",
  "baby_age_months": 3,
  "top_k": 5
}
```

| 필드 | 필수 | 검증 |
| --- | --- | --- |
| `query` | O | 2~500자 |
| `baby_age_months` | 선택 | 0~36 |
| `top_k` | 선택 | 기본 5, 1~10 |

### 공통 출력

```json
{
  "success": true,
  "answer": "검색 근거를 바탕으로 생성한 답변",
  "category": "feeding",
  "sources": [
    {
      "document_id": "uuid",
      "chunk_id": "uuid",
      "title": "문서 제목",
      "organization": "발행 기관",
      "url": "https://example.org/source",
      "verified_at": "2026-09-03",
      "score": 0.87
    }
  ],
  "confidence": "high",
  "safety_notice": null
}
```

근거가 없거나 최소 점수에 미달하면 추측하지 않고 `confidence=low`를 반환합니다.

### RAG 응답 고정값

`category`는 호출된 Tool에 따라 서버 내부에서 다음 값으로 고정합니다.

```text
search_feeding_guide      → feeding
search_sleep_guide        → sleep
search_weaning_guide      → weaning
search_development_guide  → development
search_safety_guide       → safety
```

`confidence`의 초기 MVP 허용값은 다음 두 개입니다.

```text
high
low
```

- 최소 유사도 기준을 만족하는 근거가 있으면 `high`를 반환합니다.
- 근거가 없거나 최소 유사도 기준에 미달하면 `low`를 반환합니다.
- 새로운 값을 추가할 때는 `baby_info_server`와 FastAPI의 Response Schema를 동시에 변경합니다.

출처의 `verified_at`은 `YYYY-MM-DD` 또는 `null`로 반환하고, `score`는 `0.0` 이상 `1.0` 이하의 값으로 반환합니다.

### RAG 근거 부족 응답

검색 결과가 없거나 `RAG_MIN_SIMILARITY` 기준에 미달한 경우에도 Tool 실행 자체는 성공했으므로 `success=true`를 반환합니다.

```json
{
  "success": true,
  "answer": "확인 가능한 근거를 충분히 찾지 못했습니다.",
  "category": "feeding",
  "sources": [],
  "confidence": "low",
  "safety_notice": null
}
```

- `answer`는 항상 반환합니다.
- 근거가 없으면 `sources`는 빈 목록으로 반환합니다.
- 검색 근거가 부족한 내용을 모델의 일반 지식으로 보충하지 않습니다.
- 응급 위험 표현이 포함된 경우에는 필요한 안전 안내를 `safety_notice`에 반환합니다.

### MCP Tool 실패 응답 계약

예상 가능한 입력 오류와 외부 서비스 오류는 MCP 프로세스를 중단하지 않고 구조화된 Tool 결과로 반환합니다.

```json
{
  "success": false,
  "message": "공공데이터 API를 호출할 수 없습니다.",
  "error_code": "EXTERNAL_API_ERROR"
}
```

허용 오류 코드:

| 오류 코드 | 발생 상황 |
| --- | --- |
| `INVALID_REQUEST` | 필수 입력 누락 또는 허용되지 않은 입력 |
| `VALIDATION_ERROR` | 길이·범위·형식 검증 실패 |
| `EXTERNAL_API_ERROR` | 공공데이터 API 호출 실패 또는 잘못된 응답 |
| `RAG_SERVICE_UNAVAILABLE` | PostgreSQL·pgvector·Ollama 등 RAG 구성요소 장애 |
| `ANSWER_GENERATION_FAILED` | OpenAI 답변 생성 실패 |
| `RATE_LIMIT_EXCEEDED` | 외부 서비스 호출 한도 초과 |

- 지역 검색 결과 없음은 실패가 아니며 `success=true`, `data=[]`를 반환합니다.
- RAG 근거 부족은 실패가 아니며 `success=true`, `confidence=low`를 반환합니다.
- MCP 프로세스 중단이나 복구할 수 없는 초기화 실패처럼 Tool 응답을 만들 수 없는 장애는 예외로 처리합니다.
- API Key·SQL·Stack Trace·내부 접속정보는 `message`에 포함하지 않습니다.

---

## 6. RAG 처리 흐름

```
Tool 호출
→ 입력 검증·질문 정규화
→ 응급·위험 표현 확인
→ 캐시 사용 여부 판단
→ Ollama 질의 임베딩 생성
→ 카테고리·월령·출처 필터
→ pgvector 유사도 검색
→ 최소 점수 확인
→ 상위 Chunk로 Context 구성
→ OpenAI Responses API 답변 생성
→ 출처·신뢰도·안전 안내 결합
```

### 문서 색인

1. 공식 PDF·텍스트와 메타데이터 준비
2. 본문 추출과 중복 문장 제거
3. 문단 경계를 보존해 Chunk 분할
4. 카테고리·월령·출처 연결
5. Ollama Embedding으로 문서 Chunk 벡터 생성
6. 생성된 벡터를 PostgreSQL·pgvector의 `document_chunks`에 저장
7. 샘플 질문으로 검색 품질 확인

초기 Chunk 권장값:

- 300~500 tokens
- 중첩 50~80 tokens
- 제목·문단 경계 우선 보존

---

## 7. 공용 DB 통합 계약

Backend, `baby_care_server`, `baby_info_server`가 동일한 PostgreSQL을 사용할 때 다음 규칙을 공통 계약으로 사용합니다.

### 7.1 공통 컬럼 규칙

1. ID 및 외래키 컬럼은 `VARCHAR(100)`으로 통일합니다.
2. 기본키와 이를 참조하는 외래키는 반드시 같은 자료형을 사용합니다.
3. 특정 시점을 나타내는 컬럼은 `TIMESTAMPTZ`를 사용합니다.
4. 날짜만 의미하는 값은 `DATE`를 사용합니다.
5. JSON 데이터는 PostgreSQL의 `JSONB`를 사용합니다.
6. 서버마다 같은 테이블을 별도로 생성하지 않고 테이블별 Migration 담당자를 한 명으로 지정합니다.
7. 읽기 전용 서버에는 애플리케이션 규칙뿐 아니라 가능하면 DB 권한도 읽기 전용으로 부여합니다.

시간 컬럼 기준:

| 컬럼 종류 | 자료형 | 예시 |
| --- | --- | --- |
| 발생·저장·수정 시각 | `TIMESTAMPTZ` | `recorded_at`, `created_at`, `updated_at` |
| 날짜만 의미하는 값 | `DATE` | `published_at`, `verified_at`, `birth_date` |

DB에는 절대 시점을 보존할 수 있도록 `TIMESTAMPTZ`로 저장하고, 사용자에게 보여줄 때 `APP_TIMEZONE=Asia/Seoul`을 적용합니다.

### 7.2 공용 테이블 관계

```text
babies.id VARCHAR(100)
└─ care_logs.baby_id VARCHAR(100)

documents.id VARCHAR(100)
└─ document_chunks.document_id VARCHAR(100)
```

- Backend의 `babies.id`와 `care_logs.baby_id`는 동일한 `VARCHAR(100)`을 사용합니다.
- `documents.id`와 `document_chunks.document_id`는 동일한 `VARCHAR(100)`을 사용합니다.
- `care_logs.baby_id`는 `babies.id`를 외래키로 참조합니다.
- `document_chunks.document_id`는 `documents.id`를 외래키로 참조합니다.

### 7.3 테이블별 생성·관리 담당

| 테이블 | Migration·쓰기 담당 | 조회 범위 |
| --- | --- | --- |
| `babies` | Backend | Backend 및 필요한 Care 기능 |
| `care_logs` | Backend·Care 공동 계약, Migration 담당자는 한 명으로 지정 | Backend와 `baby_care_server` |
| `documents` | `baby_info_server` | `baby_info_server`, Care는 `stool` 용도로만 사용 |
| `document_chunks` | `baby_info_server` | `baby_info_server`, Care는 `stool` Chunk만 읽기 |
| `reminder_settings` | Backend | Backend |
| `user_memories` | Backend | Backend Agent Memory Layer |

같은 테이블을 여러 서버가 각각 Migration하지 않습니다. 공동 사용 테이블도 실제 Migration 파일의 관리 담당자는 한 명으로 지정합니다.

권장 담당:

```text
babies, care_logs, reminder_settings, user_memories
→ Backend Migration에서 생성

documents, document_chunks
→ baby_info_server Migration에서 생성
```

`baby_care_server`는 `care_logs`를 사용하지만 별도의 다른 구조로 다시 생성하지 않습니다.

### 7.4 `babies`와 `care_logs` 연결 계약

```sql
CREATE TABLE babies (
    id VARCHAR(100) PRIMARY KEY
    -- 나머지 아기 정보 컬럼은 Backend 계약을 따릅니다.
);
```

`care_logs`는 Backend와 `baby_care_server`가 동일한 구조를 사용합니다.

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

`baby_info_server`는 `babies`, `care_logs` 테이블을 생성하거나 수정하지 않습니다.

### 7.5 `documents`

`documents`는 문서 단위의 원본 정보와 RAG 카테고리를 저장합니다.

```sql
CREATE TABLE documents (
    id VARCHAR(100) PRIMARY KEY,
    title TEXT NOT NULL,
    organization TEXT NOT NULL,
    source_url TEXT NOT NULL,
    category VARCHAR(30) NOT NULL,
    published_at DATE,
    verified_at DATE,
    checksum VARCHAR(64) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_documents_category
        CHECK (
            category IN (
                'feeding',
                'sleep',
                'weaning',
                'development',
                'safety',
                'stool'
            )
        )
);

CREATE INDEX idx_documents_category_active
    ON documents (category, is_active);
```

카테고리는 `documents`에만 저장합니다.

```text
feeding
sleep
weaning
development
safety
stool
```

`document_chunks`에는 `category`를 중복 저장하지 않습니다. Chunk의 카테고리는 연결된 `documents.category`를 기준으로 판단합니다.

### 7.6 `document_chunks`

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

아래 `vector(768)`의 `768`은 예시입니다. 실제 값은 선택한 `OLLAMA_EMBEDDING_MODEL`의 출력 차원 및 `EMBEDDING_DIMENSIONS`와 반드시 같아야 합니다.

```sql
CREATE TABLE document_chunks (
    id VARCHAR(100) PRIMARY KEY,
    document_id VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    age_min_months INTEGER,
    age_max_months INTEGER,
    topic TEXT,
    urgency_level VARCHAR(30),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_document_chunks_document
        FOREIGN KEY (document_id)
        REFERENCES documents(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_document_chunks_index
        UNIQUE (document_id, chunk_index),

    CONSTRAINT ck_document_chunks_age_min
        CHECK (age_min_months IS NULL OR age_min_months BETWEEN 0 AND 36),

    CONSTRAINT ck_document_chunks_age_max
        CHECK (age_max_months IS NULL OR age_max_months BETWEEN 0 AND 36),

    CONSTRAINT ck_document_chunks_age_range
        CHECK (
            age_min_months IS NULL
            OR age_max_months IS NULL
            OR age_min_months <= age_max_months
        )
);

CREATE INDEX idx_document_chunks_document
    ON document_chunks (document_id);
```

pgvector 검색 인덱스는 프로젝트에서 사용할 거리 계산 방식과 운영 데이터 규모를 확정한 후 추가합니다.

cosine distance를 사용할 경우:

```sql
CREATE INDEX idx_document_chunks_embedding_cosine
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops);
```

### 7.7 RAG 카테고리 조회 규칙

`baby_info_server`는 `documents`와 `document_chunks`를 조인하여 Tool별 카테고리를 검색합니다.

```sql
SELECT
    d.id AS document_id,
    dc.id AS chunk_id,
    d.title,
    d.organization,
    d.source_url,
    d.verified_at,
    dc.content,
    1 - (dc.embedding <=> :query_embedding) AS score
FROM document_chunks AS dc
JOIN documents AS d
    ON d.id = dc.document_id
WHERE d.is_active = TRUE
  AND d.category = :category
  AND (
        :baby_age_months IS NULL
        OR (
            (dc.age_min_months IS NULL OR dc.age_min_months <= :baby_age_months)
            AND
            (dc.age_max_months IS NULL OR dc.age_max_months >= :baby_age_months)
        )
      )
ORDER BY dc.embedding <=> :query_embedding
LIMIT :top_k;
```

월령 필터 규칙:

- `baby_age_months`가 `null`이면 월령 조건 없이 해당 카테고리 전체를 검색합니다.
- `baby_age_months`가 있으면 `age_min_months` 이상이고 `age_max_months` 이하인 Chunk를 검색합니다.
- Chunk의 `age_min_months` 또는 `age_max_months`가 `null`이면 해당 방향의 제한이 없는 자료로 처리합니다.
- 월령의 경계값은 포함합니다. 예를 들어 `age_min_months=3`, `age_max_months=6`인 Chunk는 3개월과 6개월 모두 검색 대상입니다.
- 입력 월령은 Tool Schema에서 `0~36` 범위로 먼저 검증합니다.

`baby_care_server`는 기저귀 변 분석에서 `stool` 카테고리만 읽습니다.

```sql
SELECT
    d.id AS document_id,
    dc.id AS chunk_id,
    d.title,
    d.organization,
    d.source_url,
    d.verified_at,
    dc.content,
    1 - (dc.embedding <=> :query_embedding) AS score
FROM document_chunks AS dc
JOIN documents AS d
    ON d.id = dc.document_id
WHERE d.is_active = TRUE
  AND d.category = 'stool'
  AND (
        :baby_age_months IS NULL
        OR (
            (dc.age_min_months IS NULL OR dc.age_min_months <= :baby_age_months)
            AND
            (dc.age_max_months IS NULL OR dc.age_max_months >= :baby_age_months)
        )
      )
ORDER BY dc.embedding <=> :query_embedding
LIMIT :top_k;
```

`baby_care_server`의 `stool` 검색도 `analyze_infant_stool` 입력의 `baby_age_months`를 사용하여 같은 월령 필터를 적용합니다.

`baby_care_server`는 다음 작업을 수행하지 않습니다.

- `documents` 등록·수정·삭제
- `document_chunks` 등록·수정·삭제
- `stool` 이외 카테고리 검색
- 문서 재색인

가능하면 `baby_care_server`의 DB 계정에는 `documents`, `document_chunks`에 대한 `SELECT` 권한만 부여합니다.

### 7.8 역할 구분

| 구성 | 역할 |
| --- | --- |
| Ollama | 문서 Chunk와 사용자 검색 Query를 임베딩 벡터로 변환 |
| PostgreSQL | 원본 문서·Chunk·메타데이터 저장 |
| pgvector | 임베딩 저장과 유사도 검색 |
| OpenAI Responses API | 검색된 Context로 최종 답변 생성 |

문서 Chunk와 검색 Query는 반드시 동일한 `OLLAMA_EMBEDDING_MODEL`을 사용합니다.

모델의 출력 차원과 PostgreSQL의 `embedding vector(차원)` 값도 같아야 합니다.

임베딩 모델을 변경하면 기존 문서를 다시 임베딩합니다.

```text
육아 문서
→ Chunk 분할
→ Ollama Embedding
→ PostgreSQL pgvector 저장

사용자 질문
→ 동일한 Ollama Embedding
→ pgvector 유사도 검색
→ 관련 Chunk 조회
→ OpenAI Responses API로 최종 답변 생성
```

### 7.9 DB 생성 순서

외래키 오류를 방지하기 위해 다음 순서로 Migration을 실행합니다.

```text
1. pgvector Extension
2. babies
3. care_logs
4. reminder_settings
5. user_memories
6. documents
7. document_chunks
8. 일반 인덱스
9. pgvector 검색 인덱스
10. 서버별 DB 권한
```

필수 선후 관계:

```text
babies
→ care_logs

documents
→ document_chunks
```

### 7.10 변경 규칙

공용 테이블을 변경할 때는 Backend, Care, Info 담당자가 함께 검토합니다.

다음 변경은 한 서버가 단독으로 진행하지 않습니다.

- ID 자료형 변경
- 컬럼 이름 변경
- 컬럼 삭제
- 필수 여부 변경
- 외래키 삭제 또는 참조 대상 변경
- `category` 허용값 변경
- 임베딩 모델 및 벡터 차원 변경
- pgvector 거리 계산 방식 변경

임베딩 모델이나 벡터 차원이 변경되면 기존 `document_chunks.embedding`을 그대로 사용하지 않고 전체 문서를 다시 임베딩합니다.

### 7.11 통합 확인 항목

- `babies.id`와 `care_logs.baby_id`가 모두 `VARCHAR(100)`인지 확인
- `documents.id`와 `document_chunks.document_id`가 모두 `VARCHAR(100)`인지 확인
- `care_logs` 구조가 Backend와 Care에서 동일한지 확인
- `care_logs.baby_id` 외래키가 정상 동작하는지 확인
- `document_chunks.document_id` 외래키가 정상 동작하는지 확인
- `document_chunks`에 `category`가 중복 저장되지 않는지 확인
- Care가 `category='stool'`인 문서만 조회하는지 확인
- `baby_age_months=null`일 때 카테고리 전체 월령 자료를 검색하는지 확인
- `baby_age_months`가 있을 때 월령 범위에 포함되는 Chunk만 검색하는지 확인
- `age_min_months` 또는 `age_max_months`가 `null`인 Chunk가 열린 범위로 처리되는지 확인
- 월령 최솟값·최댓값 경계가 검색 결과에 포함되는지 확인
- Care DB 계정이 RAG 테이블을 수정할 수 없는지 확인
- `created_at`, `updated_at`, `recorded_at`이 `TIMESTAMPTZ`인지 확인
- `published_at`, `verified_at`이 `DATE`인지 확인
- Ollama 임베딩 차원과 `vector(차원)`이 같은지 확인
- 임베딩 모델 변경 시 전체 재색인이 수행되는지 확인

---

## 8. 예방접종 분리

`get_vaccination_info` Tool과 예방접종 Repository를 만들지 않습니다.

예방접종은 FastAPI가 다음 파일을 직접 조회합니다.

```
backend/data/vaccinations.json
```

```
GET /api/vaccinations/{baby_id}
→ vaccination_service.py
→ vaccinations.json
```

CODEF·본인인증·실제 접종 API는 사용하지 않습니다.

---

## 9. 디렉터리 구조

```

baby_info_server/
├─ server.py
├─ config.py
├─ constants.py
│
├─ tools/
│  ├─ search_pediatric_hospitals.py
│  ├─ search_emergency_hospitals.py
│  ├─ search_feeding_guide.py
│  ├─ search_sleep_guide.py
│  ├─ search_weaning_guide.py
│  ├─ search_development_guide.py
│  └─ search_safety_guide.py
│
├─ schemas/
│  ├─ hospital.py
│  └─ knowledge.py
│
├─ services/
│  ├─ hospital_service.py
│  ├─ emergency_service.py
│  ├─ rag_service.py
│  ├─ embedding_service.py
│  └─ answer_service.py
│
├─ repositories/
│  └─ rag_repository.py
│
├─ prompts/
│  └─ rag_answer_prompt.txt
│
├─ ingestion/
│  ├─ document_loader.py
│  ├─ chunker.py
│  └─ indexer.py
│
└─ tests/
   ├─ test_hospital_tools.py
   ├─ test_rag_tools.py
   └─ test_mcp_tools.py
```

---

## 10. 환경변수

```
APP_ENV=development
APP_TIMEZONE=Asia/Seoul

PUBLIC_DATA_API_KEY=
PUBLIC_DATA_BASE_URL=

OPENAI_API_KEY=
OPENAI_RESPONSE_MODEL=

OLLAMA_BASE_URL=
OLLAMA_EMBEDDING_MODEL=
OLLAMA_TIMEOUT_SECONDS=30
EMBEDDING_DIMENSIONS=

POSTGRES_DSN=postgresql+psycopg://postgres:password@localhost:5432/baby_ai

REDIS_URL=
CACHE_TTL_SECONDS=600

RAG_TOP_K=5
RAG_MIN_SIMILARITY=0.70
RAG_MAX_CONTEXT_CHARS=8000

MCP_HOST=127.0.0.1
MCP_PORT=8102
MCP_STREAMABLE_HTTP_PATH=/mcp
```

실행 환경별 `MCP_HOST` 기준:

```text
로컬 직접 실행: MCP_HOST=127.0.0.1
Docker 등 별도 컨테이너 실행: MCP_HOST=0.0.0.0
```

컨테이너 환경의 FastAPI 연결 예:

```text
BABY_INFO_MCP_URL=http://baby-info-server:8102/mcp
```

`MCP_HOST=127.0.0.1`은 다른 컨테이너의 연결을 허용하지 않으므로 배포 환경에 맞게 설정합니다.

---

## 11. 캐시 정책

일반 육아 정보 검색과 병원 검색 결과만 Redis에 짧게 캐시할 수 있습니다.

RAG 캐시 키:

```
tool_name
+ normalized_query
+ baby_age_months
+ top_k
+ index_version
```

응급 표현이 포함된 질문과 민감정보는 캐시하지 않습니다.

Redis 장애가 발생해도 캐시 없이 검색을 계속합니다.

---

## 12. 안전 원칙

- RAG Context에 없는 사실을 만들지 않음
- 모든 답변에 확인 가능한 출처 포함
- 월령이 제공되면 해당 월령 자료 우선 검색
- 진단·처방·투약 용량 결정을 제공하지 않음
- 응급 위험 표현은 일반 답변보다 119·의료기관 안내 우선
- 병원 운영 여부는 방문 전 전화 확인 안내
- API Key·SQL·Stack Trace를 응답에 노출하지 않음

---

## 13. 필수 테스트

- 지역명 누락·길이 초과
- 공공데이터 API 실패·시간 초과
- 병원 검색 결과 없음
- 잘못된 `baby_age_months`
- RAG 검색 결과 없음·최소 점수 미달
- 월령·카테고리 필터 확인
- Ollama 연결 실패
- OpenAI 답변 생성 실패
- Redis 장애 시 캐시 없이 동작
- `get_vaccination_info`가 등록되지 않았는지 확인
- 실패 응답에 `success`, `message`, `error_code`가 포함되는지 확인
- 실패 응답에 API Key·SQL·Stack Trace가 노출되지 않는지 확인
- 전화번호·운영시간·응급실 등급이 없는 의료기관 데이터 처리
- 병원명 또는 주소가 없는 데이터를 결과에서 제외하는지 확인
- 부가 정보가 없을 때 빈 문자열 대신 `null`을 반환하는지 확인
- Tool별 고정 `category` 확인
- `confidence`가 `high` 또는 `low`만 반환되는지 확인
- 근거 부족 시 `success=true`, `sources=[]`, `confidence=low`인지 확인
- 근거 부족 답변에 모델 일반 지식이 추가되지 않는지 확인
- 출처 `score`가 `0.0~1.0` 범위인지 확인
- 로컬 및 컨테이너 환경에서 `/mcp` 연결 확인
- 약속된 Schema와 다른 응답을 FastAPI가 `INVALID_MCP_RESPONSE`로 처리하는지 확인

---

## 14. 완료 기준

- MCP Tool은 7개만 등록
- 병원 검색은 지역명만 입력
- RAG는 Ollama Embedding 사용
- RAG 테이블은 공용 `documents`, `document_chunks` 사용
- 예방접종·기저귀 분석·STT·알림을 담당하지 않음
- 모든 지식 답변에 출처와 신뢰도 포함

---
