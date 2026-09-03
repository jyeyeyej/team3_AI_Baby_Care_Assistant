# 0~36개월 영유아 AI 육아 도우미 개발계획서

<aside>
🛠️

**Python·Streamlit·FastAPI·PostgreSQL·Redis·MCP로 구현하는 테스트용 AI 육아 도우미 개발계획**

</aside>

## 1. 개발 목표

0~36개월 영유아 보호자가 육아 기록, 화면 알림, 육아 지식 검색, 기저귀 사진 관찰, 지역명 기반 의료기관 검색을 사용할 수 있는 프로토타입을 구현합니다.

## 2. 기술 스택

| 영역 | 기술 |
| --- | --- |
| 프론트엔드 | Streamlit |
| 백엔드 | FastAPI·Pydantic |
| 영구 데이터 | PostgreSQL |
| 임시 상태·캐시 | Redis |
| MCP | FastMCP·Streamable HTTP |
| 임베딩 | Ollama Embedding |
| 벡터 검색 | PostgreSQL pgvector |
| 답변·Vision·STT | OpenAI API |
| 테스트 | pytest |

Supabase는 사용하지 않습니다.

## 3. 프로토타입 범위

### 구현

- 가짜 사용자 선택 로그인
- 사용자별 아기 정보 등록·조회·수정
- 수유·수면·배변·성장 기록과 패턴
- 기록 수정·삭제
- 수유 화면 알림과 간격 설정
- 음성 파일 STT와 승인 후 기록
- 기저귀 사진 분석
- 육아 정보 RAG
- 지역명 기반 소아과·응급실 검색
- 가짜 예방접종 JSON
- 성장 그래프

### 제외

- 실제 인증·회원가입·JWT
- 푸시 알림
- 실제 예방접종 연동
- 관리자 페이지
- 채팅 내역 검색
- 영상·울음소리 분석
- 진단·처방

## 4. 서비스 구조

```mermaid
flowchart TD
    A["Streamlit UI"] --> B["FastAPI"]
    B --> C["PostgreSQL"]
    B --> D["Redis"]
    B --> E["AI Agent"]
    E --> F["baby_care_server"]
    E --> G["baby_info_server"]
    F --> C
    G --> C
```

FastAPI가 사용자·아기 범위를 확인한 뒤 Agent와 MCP를 호출합니다. MCP Tool 입력의 `baby_id`를 클라이언트가 임의로 바꿔 다른 사용자의 데이터를 조회하지 못하도록 서버에서 다시 검증합니다.

## 5. 서버 책임

### FastAPI

- 가짜 로그인·세션
- 아기 정보
- 수유 알림
- STT
- 가짜 예방접종
- 기록 수정·삭제
- AI Agent·MCP Client
- Tool 승인과 Redis 상태

### baby_care_server

- `record_care_event`
- `get_care_records`
- `analyze_infant_stool`
- `care_logs` 저장·조회
- `stool` RAG 읽기

### baby_info_server

- 5개 육아 카테고리 RAG Tool
- 소아과·응급실 Tool
- `documents`, `document_chunks` 색인·관리

## 6. DB

```
babies
care_logs
reminder_settings
documents
document_chunks
```

- `care_logs`는 수유·수면·배변·성장 기록을 `details JSONB`로 저장하는 통합 테이블입니다.
- `document_chunks.embedding`은 선택한 Ollama 모델 차원과 동일한 `vector(n)`을 사용합니다.
- 날짜·시간은 PostgreSQL에 UTC `TIMESTAMPTZ`로 저장하고 화면에는 Asia/Seoul로 표시합니다.

## 7. 핵심 흐름

### 음성 기록

```
업로드 → 파일 검증 → STT → Agent 필드 추출 → Redis 승인 대기
→ 사용자 승인 → record_care_event → care_logs 저장
```

### RAG

```
질문 → Ollama 임베딩 → 카테고리·월령 필터 → pgvector 검색
→ 아기 정보·알레르기 결합 → OpenAI Responses API → 출처 포함 답변
```

### 알림

```
마지막 확정 수유 + 설정 간격 → 화면 카드
수유했어요 → 승인·저장 → 실제 수유 시각부터 재계산
10분 후 → 현재 시각 + 10분
건너뛰기 → 기록 없이 현재 시각 + 설정 간격
```

## 8. Tool 승인

- 조회·검색: 자동 실행
- 기록·수정·삭제: 사용자 승인 필수
- 승인 전 arguments: Redis 10분 보관
- 중복 실행: `idempotency_key`로 방지
- 만료·거절: DB 변경 없음

## 9. 주요 API

| Method | Endpoint | 역할 |
| --- | --- | --- |
| POST | `/api/test-login` | 가짜 로그인 |
| POST·GET | `/api/babies` | 아기 등록·목록 |
| GET·PATCH | `/api/babies/{baby_id}` | 아기 조회·수정 |
| POST·GET | `/api/care-logs` | MCP 기록·조회 |
| PATCH·DELETE | `/api/care-logs/{log_id}` | 기록 수정·삭제 |
| GET·PATCH | `/api/reminders/...` | 알림 조회·처리·설정 |
| GET | `/api/vaccinations/{baby_id}` | 가짜 예방접종 |
| POST | `/api/speech/transcribe` | STT |
| POST | `/api/chat` | Agent 대화 |
| POST | `/api/tool-calls/{id}/approve` | 승인 실행 |
| POST | `/api/tool-calls/{id}/reject` | 승인 거절 |

## 10. Redis

| Key | 내용 | TTL 예시 |
| --- | --- | --- |
| `session:{session_id}` | 테스트 로그인·대화 상태 | 1시간 |
| `reminder:{baby_id}` | 연기·건너뛰기 상태 | 1일 |
| `tool_approval:{tool_call_id}` | 승인 대기 Tool | 10분 |
| `idempotency:{key}` | 중복 요청 결과 | 1일 |
| `hospital:{region}:{type}` | 병원 검색 캐시 | 10분 |
| `rag:{query_hash}` | RAG 결과 캐시 | 10분 |

영구 데이터는 Redis에만 저장하지 않습니다.

## 11. 환경변수

```
APP_TIMEZONE=Asia/Seoul
POSTGRES_DSN=postgresql+psycopg://postgres:password@localhost:5432/baby_ai
REDIS_URL=

OPENAI_API_KEY=
OPENAI_RESPONSE_MODEL=
OPENAI_VISION_MODEL=
OPENAI_STT_MODEL=

OLLAMA_BASE_URL=
OLLAMA_EMBEDDING_MODEL=
EMBEDDING_DIMENSIONS=

PUBLIC_DATA_API_KEY=
PUBLIC_DATA_BASE_URL=

BABY_CARE_MCP_URL=
BABY_INFO_MCP_URL=
```

## 12. 구현 순서

1. PostgreSQL·pgvector와 공통 Schema
2. FastAPI 가짜 로그인·아기 정보
3. `baby_care_server` 기록 저장·조회
4. 육아 관리 화면과 수정·삭제
5. 수유 알림·Redis
6. `baby_info_server` 문서 색인·RAG
7. 병원 검색
8. 기저귀 사진 분석
9. STT 승인 기록
10. 통합 테스트·시연 데이터

## 13. 필수 테스트

- 다른 테스트 사용자의 아기 접근 차단
- 승인 없는 기록·수정·삭제 차단
- 중복 Tool 승인·중복 기록
- 수면 중복 시작과 시작 없는 종료
- 건너뛰기 후 기록 미생성·다음 알림 계산
- STT 형식·용량·실패·승인 취소
- RAG 결과 없음·출처·월령·알레르기 확인
- Ollama 모델과 vector 차원 일치
- 병원 빈 결과·API 실패
- 기저귀 이미지 품질·Vision 실패
- 예방접종 JSON 조회

## 14. 완료 기준

- 두 MCP 서버가 각각 3개·7개 Tool만 제공
- DB 5개 테이블과 Redis 역할이 분리됨
- 사용자 승인과 중복 방지가 작동함
- Streamlit에서 전체 시나리오를 시연할 수 있음
- Swagger `/docs`와 pytest로 주요 기능을 확인할 수 있음