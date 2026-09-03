# baby_info_server 최종 개발계획서

> 0~36개월 영유아 보호자를 위한 육아 지식 RAG와 지역명 기반 소아과·응급실 조회를 제공하는 Python MCP 서버

## 1. 서버 책임

### 담당

- 수유·수면·이유식·발달·안전 육아 지식 RAG
- RAG 문서 색인과 임베딩 저장
- 공용 `documents`, `document_chunks` 관리
- 지역명 기반 실제 소아과 검색
- 지역명 기반 실제 응급실 검색
- 공식 성장 기준 데이터 조회
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

예방접종은 FastAPI가 `vaccinations.json`을 조회합니다. 기저귀 사진은 `baby_care_server`의 `analyze_infant_stool`이 처리합니다.

## 2. 기술 구성

| 영역 | 기술 |
|---|---|
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

```text
/mcp
```

## 3. MCP Tool 목록

예방접종 Tool을 제외한 7개를 제공합니다.

### 의료기관 Tool

| Tool | 역할 |
|---|---|
| `search_pediatric_hospitals` | 지역명 기반 소아과 검색 |
| `search_emergency_hospitals` | 지역명 기반 응급실 검색 |

### 육아 지식 RAG Tool

| Tool | 고정 카테고리 | 검색 범위 |
|---|---|---|
| `search_feeding_guide` | `feeding` | 모유·분유·수유량·수유 간격·트림 |
| `search_sleep_guide` | `sleep` | 월령별 수면·낮잠·수면 안전 |
| `search_weaning_guide` | `weaning` | 이유식 시기·단계·식재료·알레르기 주의 |
| `search_development_guide` | `development` | 신체·인지·언어·사회성 발달 |
| `search_safety_guide` | `safety` | 낙상·질식·화상·카시트 등 |

총 MCP Tool은 7개입니다.

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

```text
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
|---|---:|---|
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

## 6. RAG 처리 흐름

```text
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
5. Ollama Embedding으로 벡터 생성
6. 생성된 벡터를 PostgreSQL·pgvector의 `document_chunks`에 저장
7. 샘플 질문으로 검색 품질 확인

초기 Chunk 권장값:

- 300~500 tokens
- 중첩 50~80 tokens
- 제목·문단 경계 우선 보존

## 7. 공용 RAG DB

### `documents`

```text
id
title
organization
source_url
category
published_at
verified_at
checksum
is_active
created_at
updated_at
```

카테고리:

```text
feeding
sleep
weaning
development
safety
stool
```

### `document_chunks`

```text
id
document_id
content
chunk_index
age_min_months
age_max_months
topic
urgency_level
metadata
embedding
created_at
```

`baby_info_server`가 모든 문서를 색인·관리합니다. `baby_care_server`는 `stool` 카테고리를 읽기 전용으로 조회합니다.

임베딩 모델과 벡터 차원은 두 서버에서 동일해야 합니다.

역할은 다음과 같이 구분합니다.

| 구성 | 역할 |
|---|---|
| Ollama | 문서 Chunk와 사용자 질문을 임베딩 벡터로 변환 |
| PostgreSQL | 원본 문서·Chunk·메타데이터 저장 |
| pgvector | 임베딩 저장과 유사도 검색 |
| OpenAI Responses API | 검색된 Context로 최종 답변 생성 |

문서와 사용자 질문은 반드시 동일한 `OLLAMA_EMBEDDING_MODEL`을 사용합니다. 모델의 출력 차원과 PostgreSQL의 `embedding vector(차원)` 값도 같아야 합니다. 임베딩 모델을 변경하면 기존 문서를 다시 임베딩합니다.

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

## 8. 예방접종 분리

`get_vaccination_info` Tool과 예방접종 Repository를 만들지 않습니다.

예방접종은 FastAPI가 다음 파일을 직접 조회합니다.

```text
backend/data/vaccinations.json
```

```text
GET /api/vaccinations/{baby_id}
→ vaccination_service.py
→ vaccinations.json
```

CODEF·본인인증·실제 접종 API는 사용하지 않습니다.

## 9. 디렉터리 구조

```text
baby_info_server/
├─ server.py
├─ config.py
├─ constants.py
├─ tools/
│  ├─ hospital_tools.py
│  ├─ emergency_tools.py
│  ├─ feeding_guide_tool.py
│  ├─ sleep_guide_tool.py
│  ├─ weaning_guide_tool.py
│  ├─ development_guide_tool.py
│  └─ safety_guide_tool.py
├─ schemas/
│  ├─ hospital.py
│  └─ knowledge.py
├─ services/
│  ├─ hospital_service.py
│  ├─ emergency_service.py
│  ├─ rag_service.py
│  ├─ embedding_service.py
│  └─ answer_service.py
├─ repositories/
│  └─ rag_repository.py
├─ ingestion/
│  ├─ document_loader.py
│  ├─ chunker.py
│  └─ indexer.py
└─ tests/
   ├─ test_hospital_tools.py
   ├─ test_rag_tools.py
   └─ test_mcp_tools.py
```

## 10. 환경변수

```text
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

## 11. 캐시 정책

일반 육아 정보 검색과 병원 검색 결과만 Redis에 짧게 캐시할 수 있습니다.

RAG 캐시 키:

```text
tool_name + normalized_query + baby_age_months + top_k + index_version
```

응급 표현이 포함된 질문과 민감정보는 캐시하지 않습니다. Redis 장애가 발생해도 캐시 없이 검색을 계속합니다.

## 12. 안전 원칙

- RAG Context에 없는 사실을 만들지 않음
- 모든 답변에 확인 가능한 출처 포함
- 월령이 제공되면 해당 월령 자료 우선 검색
- 진단·처방·투약 용량 결정을 제공하지 않음
- 응급 위험 표현은 일반 답변보다 119·의료기관 안내 우선
- 병원 운영 여부는 방문 전 전화 확인 안내
- API Key·SQL·Stack Trace를 응답에 노출하지 않음

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

## 14. 완료 기준

- MCP Tool은 7개만 등록
- 병원 검색은 지역명만 입력
- RAG는 Ollama Embedding 사용
- RAG 테이블은 공용 `documents`, `document_chunks` 사용
- 예방접종·기저귀 분석·STT·알림을 담당하지 않음
- 모든 지식 답변에 출처와 신뢰도 포함
