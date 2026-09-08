-- Care Server 로컬 테스트에서만 사용하는 아기입니다.
-- 공용 Backend babies 스키마의 NOT NULL 컬럼을 모두 채웁니다.
INSERT INTO babies (
    id,
    user_id,
    baby_name,
    birth_date,
    gender,
    feeding_type,
    allergies
)
VALUES (
    'baby-001',
    'user-001',
    '테스트 아기',
    DATE '2026-08-03',
    'female',
    'formula',
    '[]'::jsonb
)
ON CONFLICT (id) DO UPDATE
SET
    user_id = EXCLUDED.user_id,
    baby_name = EXCLUDED.baby_name,
    birth_date = EXCLUDED.birth_date,
    gender = EXCLUDED.gender,
    feeding_type = EXCLUDED.feeding_type,
    allergies = EXCLUDED.allergies;
