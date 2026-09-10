# 데이터베이스 ERD

현재 PostgreSQL 모델과 RAG 스키마를 기준으로 작성한 물리 ERD입니다.

```mermaid
erDiagram
    BABIES ||--o{ CARE_LOGS : "baby_id"
    BABIES ||--o| REMINDER_SETTINGS : "baby_id"
    DOCUMENTS ||--o{ DOCUMENT_CHUNKS : "document_id"

    BABIES {
        varchar id PK
        varchar user_id "indexed logical owner"
        varchar baby_name
        date birth_date
        varchar gender
        float current_weight_kg
        float current_height_cm
        varchar feeding_type
        jsonb allergies
        timestamptz created_at
        timestamptz updated_at
    }

    CARE_LOGS {
        varchar id PK
        varchar baby_id FK
        varchar log_type
        timestamptz recorded_at
        jsonb details
        varchar idempotency_key UK
        timestamptz created_at
        timestamptz updated_at
    }

    REMINDER_SETTINGS {
        varchar id PK
        varchar baby_id FK_UK
        int feeding_interval_minutes
        timestamptz created_at
        timestamptz updated_at
    }

    USER_MEMORIES {
        varchar id PK
        varchar user_id "indexed logical owner"
        varchar memory_type
        text content
        jsonb tags
        timestamptz created_at
        timestamptz updated_at
    }

    DOCUMENTS {
        varchar id PK
        text title
        text organization
        text source_url
        date verified_at
        varchar category
        timestamptz created_at
    }

    DOCUMENT_CHUNKS {
        varchar id PK
        varchar document_id FK
        text content
        int chunk_index
        int age_min_months
        int age_max_months
        jsonb metadata
        vector embedding "768 dimensions"
        timestamptz created_at
    }
```

## 관계 요약

- `babies` 1 : N `care_logs`: 한 아기의 수유·수면·배변·성장 기록
- `babies` 1 : 0..1 `reminder_settings`: 아기별 수유 알림 설정 하나
- `documents` 1 : N `document_chunks`: RAG 원문과 검색 단위 청크
- `user_memories.user_id`, `babies.user_id`는 현재 사용자 식별자를 저장하지만, `users` 테이블 및 물리 FK는 아직 구현되지 않았습니다.
