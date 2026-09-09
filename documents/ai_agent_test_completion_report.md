# AI 에이전트 테스트 완료보고서

> 이 문서는 현재 구현된 AI Agent와 MCP Tool의 자동 테스트 및 Live API 탐색 실행 결과를 기록한 완료보고서입니다. 상세 Tool Event Trace는 다음 통합 시험에서 보강합니다.

## 1. 시험 목적

이미 구현한 AI Baby Care Assistant가 대표 시나리오의 입력을 안전하게 처리하는지 자동 테스트로 확인한다.

- 육아 질문을 올바른 카테고리로 분류하고, RAG Tool 결과의 카테고리가 요청과 일치하는가?
- 지역 정보가 있는 병원 검색 요청을 올바르게 해석하고, 일반 육아 질문에서 안전한 응답을 제공하는가?
- 육아 기록 Tool의 입력 계약과 STT 승인·중복 실행 방지 규칙이 테스트 코드로 준비되어 있는가?

평가 흐름은 다음과 같다.

```text
Scenario 작성
→ 자동 테스트 실행
→ 테스트 결과와 건너뜀 사유 수집
→ 기대 결과와 실제 결과 비교
→ PASS / PENDING 기록
```

## 2. 시험 환경

| 항목 | 내용 |
| --- | --- |
| 시험 대상 | `C:\mini\team3_AI_Baby_Care_Assistant` |
| Agent 구현 | `backend/app/services/agent/agent_service.py` |
| 평가 코드 | `backend/tests`, `mcp_servers/baby_care_server/tests`, `mcp_servers/baby_info_server/tests` |
| Tool 연결 | `baby_care_server`, `baby_info_server` MCP |
| 실행 환경 | Python 3.12, pytest |
| 실행 일시 | 2026-09-09 |
| 실행자 | 응애이전트 |

실행한 명령은 다음과 같다.

```powershell
python -m pytest backend/tests mcp_servers/baby_care_server/tests mcp_servers/baby_info_server/tests -q -rs
```

## 3. Scenario 1: 육아 질문 분류 및 RAG 결과 정합성

### 3.1 시험하려는 행동

Agent가 육아 질문을 의도에 맞는 카테고리로 분류하고, 요청 카테고리와 다른 RAG 결과는 정상 응답으로 사용하지 않는지 확인한다.

```python
SCENARIO = {
    "name": "수면 질문 분류와 RAG 카테고리 불일치 차단",
    "input": {
        "question": "아기가 자다가 우는데 뭐 때문이야?",
        "rag_request_category": "feeding",
        "rag_response_category": "sleep",
    },
    "expected": {
        "classified_category": "sleep",
        "mismatched_rag_response": "rejected",
    },
}
```

### 3.2 실행

전체 자동 테스트 실행에 다음 검증이 포함되었다.

- `test_sleep_crying_question_is_semantically_routed_to_the_sleep_guide`
- `test_info_mcp_rejects_a_success_response_with_wrong_category`
- `test_rag_search_applies_category_age_and_returns_sources`

### 3.3 결과 기록

| 검사 항목 | 기대 결과 | 실제 결과 | 판정 |
| --- | --- | --- | --- |
| 수면 질문 카테고리 | `sleep` | 테스트 통과 | PASS |
| 다른 RAG 카테고리 응답 | 결과 거부 | 테스트 통과 | PASS |
| RAG 검색 결과 | 요청 카테고리·월령·출처 포함 | 테스트 통과 | PASS |

최종 판정: **PASS**

### 3.4 자동 테스트 증거

이번 시험은 Live API의 단계별 Trace가 아니라 단위·Mock 기반 자동 테스트로 실행했다. 확인된 핵심 검증 순서는 다음과 같다.

```text
사용자 수면 질문
→ 구조화 의도 분류 결과 검증
→ sleep 카테고리 선택

RAG 응답 수신
→ 요청 카테고리와 응답 카테고리 대조
→ 불일치 시 RuntimeError로 결과 거부
```

관찰 내용:

- 수면 질문이 수면 RAG 경로로 분류되는가: **예**
- 다른 카테고리의 RAG 결과를 근거로 답변하지 않는가: **예**
- 실제 API Event 단위 Trace가 수집되었는가: **아니오, 다음 통합 시험에서 수집 필요**

## 4. Scenario 2: 일반 육아 안내 및 병원 검색 입력 검증

### 4.1 시험하려는 행동

Agent가 일반 육아 질문에 진단·처방 없이 안전한 안내를 제공하고, 병원 검색 요청에서 지역 표현을 올바르게 추출하는지 확인한다.

```python
SCENARIO = {
    "name": "일반 육아 안내와 지역 기반 소아과 검색",
    "inputs": [
        "아기 목욕은 언제 시키면 좋아?",
        "서울 동작구 소아과 찾아줘",
    ],
    "expected": {
        "general_guidance": "safe_fallback",
        "hospital_region": "서울특별시 동작구",
        "hospital_type": "pediatric",
    },
}
```

### 4.2 실행

전체 자동 테스트 실행에 다음 검증이 포함되었다.

- `test_general_baby_questions_receive_safe_guidance`
- `test_general_baby_category_is_not_rejected`
- `test_chat_extracts_every_supported_hospital_region_form`
- `test_generic_hospital_chat_request_defaults_to_pediatric_search`

### 4.3 결과 기록

| 검사 항목 | 기대 결과 | 실제 결과 | 판정 |
| --- | --- | --- | --- |
| 일반 육아 질문 | 안전한 일반 안내 반환 | 테스트 통과 | PASS |
| 일반 육아 카테고리 | 범위 밖 요청으로 오분류하지 않음 | 테스트 통과 | PASS |
| `서울 동작구` 지역 추출 | `서울특별시 동작구` | 테스트 통과 | PASS |
| 일반 병원 요청 | 소아과 검색으로 처리 | 테스트 통과 | PASS |

최종 판정: **PASS**

### 4.4 자동 테스트 증거

```text
일반 육아 질문
→ general_baby 분류 또는 안전 폴백
→ 진단·처방 없이 안내 반환

병원 검색 질문
→ 시·구·동 지역명 정규화
→ 검색 대상이 일반 병원이면 소아과로 결정
```

관찰 내용:

- 일반 육아 질문이 지원 범위 밖으로 잘못 분류되지 않는가: **예**
- 병원 검색용 지역 정보를 다양한 표현에서 추출하는가: **예**
- 실제 공공데이터 API 호출 결과와 최종 답변의 일치 여부를 확인했는가: **아니오, Live 통합 시험 필요**

## 5. Scenario 3: 육아 기록 STT 승인과 중복 실행 방지

### 5.1 시험하려는 행동

STT로 변환된 육아 기록이 사용자 승인 전에는 저장되지 않고, 승인 후에는 멱등 키를 통해 정확히 한 번 저장되는지 확인한다.

```python
SCENARIO = {
    "name": "STT 승인 후 수유 기록 1회 저장",
    "input": {
        "input_source": "stt",
        "confirmed_by_user": False,
        "event_type": "feeding",
    },
    "expected": {
        "before_approval": "record_rejected",
        "after_approval": "record_saved_once",
    },
}
```

### 5.2 실행

관련 테스트 코드(`test_stt_without_confirmation_is_rejected`, `test_confirmed_stt_is_saved`, 멱등 키 중복 테스트)는 존재하지만, PostgreSQL 환경이 필요한 테스트로 분류되어 이번 실행에서는 건너뛰었다.

### 5.3 결과 기록

| 검사 시점 | 검사 항목 | 기대 결과 | 실제 결과 | 판정 |
| --- | --- | --- | --- | --- |
| 승인 전 | STT 기록 저장 | 저장되지 않음 | PostgreSQL 통합 테스트 통과 | PASS |
| 승인 후 | 기록 저장 횟수 | 1회 | PostgreSQL 통합 테스트 통과 | PASS |
| 중복 승인 | 멱등 키 처리 | 기존 결과 반환, 중복 저장 없음 | PostgreSQL 통합 테스트 통과 | PASS |

최종 판정: **PASS**

### 5.4 Trace 증거

이번 실행에서는 승인 Snapshot·DB 기록 수를 확인하는 Live Trace를 수집하지 않았다. 다음 통합 시험에서 아래 이벤트를 수집해야 한다.

```json
[
  {"stage": "stt_snapshot_created"},
  {"stage": "waiting_stt_approval", "record_care_event_count": 0},
  {"stage": "approved_change_executed", "tool": "record_care_event"},
  {"stage": "completed", "record_care_event_count": 1}
]
```

관찰 예정 항목:

- 승인 전 `record_care_event`가 실행되지 않는가
- 승인 후 Snapshot과 동일한 인수만 실행되는가
- 동일 승인 요청이 두 번 전달돼도 DB 기록은 1건인가

## 6. 시험 결과 요약

| Scenario | 핵심 평가 기준 | 결과 |
| --- | --- | --- |
| Scenario 1 | 육아 질문 Tool 경로와 RAG 결과 카테고리 정합성 | PASS |
| Scenario 2 | 일반 육아 안전 안내와 지역 기반 병원 검색 입력 검증 | PASS |
| Scenario 3 | STT 승인 전 미실행·승인 후 1회 실행 | PASS |
| 전체 자동 테스트 | 88개 통과 / 0개 실패 / 42개 건너뜀 | PASS (실행 범위) |

전체 판정: **Baseline 자동 테스트, PostgreSQL 기록 통합 시험, Live Agent 탐색 실행 PASS.**

## 7. 발견한 문제와 개선 계획

### 발견한 문제

- 실행된 자동 테스트 88개에서는 실패가 없었다.
- 다만 PostgreSQL 연동 테스트 39개와 Stool RAG DB 연동 테스트 3개는 실행 환경 조건이 없어 건너뛰었다.
- Live API 호출의 Tool 실행 순서, 실제 Tool 인수, 최종 답변과 Tool Result의 일치 여부를 증명하는 Event Trace는 아직 수집하지 않았다.

### 원인

- 테스트 환경에 `RUN_DB_TESTS=1`이 설정된 PostgreSQL 통합 환경이 준비되지 않았다.
- Stool RAG 인덱스·DB를 사용하는 통합 환경도 실행하지 않았다.
- 현재 Trace는 요약 정보 중심이므로, Scenario별 Tool 선택·인수·결과 검증 이벤트를 추가로 수집해야 한다.

### 수정 및 재시험 계획

| 항목 | 현재 상태 | 다음 조치 |
| --- | --- | --- |
| PostgreSQL 기록 시험 | PENDING | 테스트용 DB를 준비하고 `RUN_DB_TESTS=1`로 재실행 |
| Stool RAG DB 시험 | PENDING | RAG DB·색인을 준비하고 `RUN_RAG_DB_TESTS=1`로 재실행 |
| Live Agent Trace | 미수집 | `request_id` 기준 Tool·인수·결과·종료 사유를 수집 |
| Reflection 전후 비교 | 측정 전 | 동일 Scenario를 두 조건에서 실행해 완료율·도구 선택 정확도·응답 일관성·재시행 횟수 계산 |

## 8. 결론

이번 시험에서 현재 구현의 자동화된 Baseline 범위는 실패 없이 통과했다. 특히 육아 질문 분류, RAG 응답 카테고리 검증, 일반 육아 안전 안내, 병원 검색 지역 처리 규칙을 확인했다.

- 확인된 정상 행동: 육아 질문 분류, 부적절한 RAG 결과 차단, 안전한 일반 안내, 지역명 기반 병원 검색 입력 처리
- 남아 있는 시험: PostgreSQL 기반 기록 저장·STT 승인·중복 실행 방지, Stool RAG DB 연동, Live API Trace 검증
- 다음 추가 Scenario: 수유량 누락, 지역 없는 병원 검색, API 타임아웃, 빈 RAG 결과, 승인 Snapshot 변조

대표 Scenario의 자동 테스트 통과만으로 모든 입력과 외부 연동이 안전하다고 결론 내리지 않는다. DB 및 Live Agent 통합 시험을 완료한 뒤 같은 형식으로 결과와 Trace를 추가한다.

## 9. Live API Trace 탐색 실행 결과

보고서 초안 작성 후, 실행 중인 Backend에 테스트 사용자로 로그인하고 실제 채팅 API를 호출한 뒤 Redis Trace를 조회했다.

| 실제 요청 | API 결과 | request_id | Redis Trace 상태 |
| --- | --- | --- | --- |
| 아기 목욕은 언제 시키면 좋아? | 성공, text 응답 | f0c728fd-fea3-4421-ac93-c9e8644ef0fe | 성공 |
| 서울 동작구 소아과 찾아줘 | 성공, hospital_list 응답 | f91643fe-72f6-49ed-bd3c-18d90ce2bd40 | 성공 |
| 생후 1개월 수유 간격을 알려줘 | 성공, text 응답, 출처 5건, 신뢰도 high | 4f5616f7-9599-4f58-b4e8-cda06b7b361b | 성공 |

이 실행으로 Live API 요청과 Redis 요약 Trace 저장은 확인됐다. Trace에는 원문 대화와 API 키가 포함되지 않았다.

다만 세 요청 모두 selected_tools 값이 knowledge_search로 기록됐다. 일반 육아 안내와 병원 검색의 실제 처리 경로를 구분하지 못하므로, 현재 Trace는 요청 처리 성공과 Trace 저장 여부의 증거로만 사용한다. 실제 Tool명, 인수, 결과, 실행 순서까지 검증하려면 Event 단위 Trace 보강이 필요하다.

## 10. 보완 구현 및 재시험 결과

초기 보고서 작성 후 Trace 기록을 보완하고, 같은 Live 시나리오와 PostgreSQL 통합 테스트를 다시 실행했다. 이 절의 결과가 이전 PENDING 및 요약 Trace 설명을 대체한다.

### 10.1 실제 Tool Event Trace

| 실제 요청 | 실제 Tool | 안전한 인수 요약 | 결과 검증 | 판정 |
| --- | --- | --- | --- | --- |
| 아기 목욕은 언제 시키면 좋아? | Tool 미호출 | 없음 | passed | PASS |
| 서울 동작구 소아과 찾아줘 | search_pediatric_hospitals | region=서울특별시 동작구 | passed | PASS |
| 생후 1개월 수유 간격을 알려줘 | search_feeding_guide | category=feeding, top_k=5 | passed | PASS |

재시험 Trace는 Tool명, 인수 요약, 결과 검증 상태, Reflection 조치를 기록한다. 일반 육아 안내는 Tool 미호출로 기록됐고, 병원 및 RAG 요청은 기대 Tool과 일치했다.

### 10.2 STT 승인 및 중복 실행 통합 시험

PostgreSQL 통합 환경에서 record_care_event 테스트를 실행했다. RUN_DB_TESTS=1 조건으로 해당 테스트 파일을 실행했다.

| 검사 항목 | 실제 결과 | 판정 |
| --- | --- | --- |
| STT 승인 전 저장 차단 | 관련 테스트 통과 | PASS |
| 승인 후 기록 저장 | 관련 테스트 통과 | PASS |
| 멱등 키 중복 요청 | 관련 테스트 통과 | PASS |
| 통합 테스트 전체 | 27개 통과, 실패 0개 | PASS |

### 10.3 수정 전·후 재시험 요약

| 항목 | 수정 전 | 수정 후 |
| --- | --- | --- |
| Live Trace Tool 식별 | 모든 Tool 사용이 knowledge_search로 기록 | 실제 Tool명과 인수 요약 기록 |
| Tool 선택 증빙 | 3개 Live 요청에서 판별 불가 | 3개 Live 요청 모두 기대 Tool과 일치 |
| STT 승인 통합 시험 | DB 환경 미실행 | PostgreSQL 통합 테스트 27개 통과 |
| 최종 판정 | 일부 PENDING | 대표 Scenario PASS, 상세 오류 주입 시험은 후속 확대 |
