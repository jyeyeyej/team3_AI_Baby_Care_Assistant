-- 생활 패턴 분석 데모용 최근 7일 시드입니다.
-- 실행 시점의 DB CURRENT_DATE를 기준으로 오늘 포함 7일을 생성합니다.
-- 고정 idempotency_key를 사용하므로 여러 번 실행해도 중복되지 않습니다.

WITH demo_days AS (
    SELECT generate_series(CURRENT_DATE - 6, CURRENT_DATE, INTERVAL '1 day')::date AS care_date
),
feeding_slots AS (
    SELECT * FROM (VALUES
        (1, TIME '07:00', 120),
        (2, TIME '11:00', 100),
        (3, TIME '15:00', 110),
        (4, TIME '19:00', 120),
        (5, TIME '23:00', 90)
    ) AS slots(slot_no, event_time, amount_ml)
),
diaper_slots AS (
    SELECT * FROM (VALUES
        (1, TIME '08:30', true, false),
        (2, TIME '13:30', true, true),
        (3, TIME '20:30', true, false)
    ) AS slots(slot_no, event_time, urine, stool)
),
sleep_slots AS (
    SELECT * FROM (VALUES
        (1, TIME '09:30', TIME '11:00'),
        (2, TIME '21:30', TIME '06:30')
    ) AS slots(slot_no, start_time, end_time)
)
INSERT INTO care_logs (id, baby_id, log_type, recorded_at, details, idempotency_key)
SELECT
    'demo-week-minjun-feeding-' || to_char(d.care_date, 'YYYYMMDD') || '-' || f.slot_no,
    'baby-002', 'feeding', d.care_date + f.event_time,
    jsonb_build_object('feeding_type', 'formula', 'amount_ml', f.amount_ml, 'source', 'demo_week_seed'),
    'demo-week-minjun-feeding-key-' || to_char(d.care_date, 'YYYYMMDD') || '-' || f.slot_no
FROM demo_days d CROSS JOIN feeding_slots f
UNION ALL
SELECT
    'demo-week-minjun-diaper-' || to_char(d.care_date, 'YYYYMMDD') || '-' || x.slot_no,
    'baby-002', 'diaper', d.care_date + x.event_time,
    jsonb_build_object('urine', x.urine, 'stool', x.stool, 'source', 'demo_week_seed'),
    'demo-week-minjun-diaper-key-' || to_char(d.care_date, 'YYYYMMDD') || '-' || x.slot_no
FROM demo_days d CROSS JOIN diaper_slots x
UNION ALL
SELECT
    'demo-week-minjun-sleep-start-' || to_char(d.care_date, 'YYYYMMDD') || '-' || s.slot_no,
    'baby-002', 'sleep',
    CASE WHEN s.slot_no = 2 THEN (d.care_date - 1) + s.start_time ELSE d.care_date + s.start_time END,
    jsonb_build_object('action', 'start', 'source', 'demo_week_seed'),
    'demo-week-minjun-sleep-start-key-' || to_char(d.care_date, 'YYYYMMDD') || '-' || s.slot_no
FROM demo_days d CROSS JOIN sleep_slots s
UNION ALL
SELECT
    'demo-week-minjun-sleep-end-' || to_char(d.care_date, 'YYYYMMDD') || '-' || s.slot_no,
    'baby-002', 'sleep',
    CASE WHEN s.slot_no = 2 THEN d.care_date + s.end_time ELSE d.care_date + s.end_time END,
    jsonb_build_object('action', 'end', 'source', 'demo_week_seed'),
    'demo-week-minjun-sleep-end-key-' || to_char(d.care_date, 'YYYYMMDD') || '-' || s.slot_no
FROM demo_days d CROSS JOIN sleep_slots s
ON CONFLICT (idempotency_key) DO NOTHING;
