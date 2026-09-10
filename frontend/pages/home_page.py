from __future__ import annotations
from html import escape

import streamlit as st

import api
from common import render_page_header


def render() -> None:
    baby = api.get_baby(st.session_state.baby_id, user_id=st.session_state.user_id, session_id=st.session_state.session_id)["data"]
    data = api.get_dashboard(st.session_state.baby_id)["data"]
    vaccine = data["next_vaccination"]
    summary_result = api.get_care_summary(
        st.session_state.baby_id,
        user_id=st.session_state.user_id,
        session_id=st.session_state.session_id,
    )
    summary = summary_result.get("data", {}) if summary_result.get("success") else {}
    feeding_summary = summary.get("feeding", {})
    sleep_summary = summary.get("sleep", {})
    diaper_summary = summary.get("diaper", {})
    feeding_interval_minutes = feeding_summary.get("average_interval_minutes")
    if isinstance(feeding_interval_minutes, (int, float)):
        feeding_hours, feeding_minutes = divmod(round(feeding_interval_minutes), 60)
        feeding_interval_label = f"{feeding_hours}시간" + (f" {feeding_minutes}분" if feeding_minutes else "")
    else:
        feeding_interval_minutes = 0
        feeding_interval_label = "기록이 더 필요해요"
    daily_feeding_label = f"{feeding_summary.get('daily_average_count', 0):.1f}"
    daily_sleep_label = f"{sleep_summary.get('daily_average_minutes', 0) / 60:.1f}시간"
    daily_diaper_label = f"{diaper_summary.get('daily_average_stool_count', 0):.1f}"
    reminder = api.get_feeding_reminder(
        st.session_state.baby_id,
        user_id=st.session_state.user_id,
        session_id=st.session_state.session_id,
    )
    alert_minutes = int(reminder["data"]["feeding_interval_minutes"]) if reminder["success"] else 180
    alert_interval_label = (
        f"{alert_minutes // 60}시간 {alert_minutes % 60}분"
        if alert_minutes % 60
        else f"{alert_minutes // 60}시간"
    )
    # Home chart scale: 2h=126, 3h=92, 4h=58, 5h=24.
    feeding_reference_y = max(24, min(126, 194 - (34 * (alert_minutes / 60))))
    chart_points = []
    for index, point in enumerate(feeding_summary.get("daily_intervals", [])[:7]):
        value = point.get("average_interval_minutes")
        hours = value / 60 if isinstance(value, (int, float)) else None
        y = 126 - ((hours - 2) / 3 * 102) if hours is not None else None
        chart_points.append((48 + (60 * index), y, point.get("weekday", "")))
    while len(chart_points) < 7:
        chart_points.append((48 + (60 * len(chart_points)), None, ""))
    chart_path_parts = []
    previous_missing = True
    for x, y, _ in chart_points:
        if y is None:
            previous_missing = True
            continue
        chart_path_parts.append(("M" if previous_missing else "L") + f"{x:.0f} {y:.1f}")
        previous_missing = False
    feeding_chart_path = " ".join(chart_path_parts)
    feeding_chart_circles = "".join(f"<circle cx='{x:.0f}' cy='{y:.1f}' r='3.5'/>" for x, y, _ in chart_points if y is not None)
    feeding_chart_weekdays = "".join(f"<text x='{x - 6:.0f}' y='149'>{escape(label)}</text>" for x, _, label in chart_points)
    current_weight = float(baby["current_weight_kg"])
    # SVG graph: 3kg=75, 4kg=55, 5kg=35. Keep the latest point visible.
    growth_y = max(24, min(135, 135 - (20 * current_weight)))
    growth_label_y = max(20, growth_y - 10)
    current_height = float(baby["current_height_cm"])
    height_y = max(24, min(135, 116 - ((current_height - 50) * 8)))
    height_label_y = max(20, height_y - 10)
    render_page_header(
        f"안녕하세요, {baby['baby_name']} 보호자님 👋",
        f"{baby['baby_name']}는 오늘 생후 {baby['age_days']}일이에요.",
        baby,
    )

    st.markdown(
        f"""
        <style>
        .home-reminder{{background:#EEF1FF;border:1px solid #C9D2FF;border-radius:15px;padding:18px 20px;margin:8px 0 16px}}.home-reminder b{{font-size:16px}}.home-sub,.home-label{{font-size:14px;color:#778198}}.home-card{{background:#fff;border:1px solid #E3E7F1;border-radius:16px;padding:16px;box-sizing:border-box;margin-bottom:14px}}.home-title{{font-weight:800;font-size:17px;margin-bottom:14px}}.home-stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}}.home-stat{{background:#F4F6FB;border-radius:10px;padding:12px 10px;min-height:76px}}.home-value{{font-weight:800;font-size:16px}}.home-unit{{color:#6374DC;font-size:12px;font-weight:700}}.growth-chart,.feeding-chart{{width:100%;height:auto;display:block;margin-top:4px}}.feeding-legend{{display:flex;gap:13px;color:#778198;font-size:11px;margin-top:3px}}.vaccine-date{{display:inline-block;background:#EEF1FF;color:#6374DC;border-radius:10px;padding:10px;font-weight:800}}@media(max-width:700px){{.home-unit{{display:block;margin-top:4px}}}}
        </style>
        <div class="home-reminder"><div><b>🍼 마지막 수유 후 {alert_interval_label}이 지났어요</b><div class="home-sub">{escape(baby['baby_name'])}의 배고픔 신호를 확인해 주세요.</div></div></div>
        """,
        unsafe_allow_html=True,
    )

    records_column, assistant_column = st.columns([1.55, 1], gap="medium")
    with records_column:
        st.markdown(
            f'''<div class="home-card"><div class="home-title">최근 7일 육아 기록</div><div class="home-stats"><div class="home-stat"><div class="home-label">수유</div><div class="home-value">{daily_feeding_label} <span class="home-unit">하루 평균</span></div></div><div class="home-stat"><div class="home-label">수면</div><div class="home-value">{daily_sleep_label} <span class="home-unit">하루 평균</span></div></div><div class="home-stat"><div class="home-label">배변</div><div class="home-value">{daily_diaper_label} <span class="home-unit">하루 평균</span></div></div></div></div><div class="home-card"><div class="home-title">최근 7일 수유 간격</div><div class="home-label">알림 간격 {alert_interval_label} 기준</div><svg class="feeding-chart" viewBox="0 0 430 155"><path d="M38 24H418 M38 58H418 M38 92H418 M38 126H418" stroke="#E3E7F1" stroke-dasharray="3 3"/><path d="M38 {feeding_reference_y}H418" stroke="#F2A365" stroke-width="2" stroke-dasharray="5 4"/><path d="{feeding_chart_path}" fill="none" stroke="#6374DC" stroke-width="3"/><g fill="#6374DC">{feeding_chart_circles}</g><g fill="#778198" font-size="10"><text x="3" y="28">5시간</text><text x="3" y="62">4시간</text><text x="3" y="96">3시간</text><text x="3" y="130">2시간</text>{feeding_chart_weekdays}</g></svg><div class="feeding-legend"><span><b style="color:#6374DC">●</b> 서아의 기록</span><span><b style="color:#F2A365">●</b> 평균 수유 간격 ({feeding_interval_label})</span></div></div><div class="home-card"><div class="home-title">몸무게 성장</div><div class="home-label">같은 성별·월령 기준과 비교한 참고 그래프</div><svg class="growth-chart" viewBox="0 0 430 180"><path d="M42 32H410 M42 72H410 M42 112H410 M42 145H410" stroke="#E3E7F1" stroke-dasharray="3 3"/><path d="M52 119 L140 103 L228 86 L316 67 L402 {growth_y}" fill="none" stroke="#6374DC" stroke-width="3"/><g fill="#6374DC"><circle cx="52" cy="119" r="4"/><circle cx="140" cy="103" r="4"/><circle cx="228" cy="86" r="4"/><circle cx="316" cy="67" r="4"/><circle cx="402" cy="{growth_y}" r="4"/></g><g fill="#778198" font-size="11"><text x="4" y="36">5kg</text><text x="4" y="76">4kg</text><text x="4" y="116">3kg</text><text x="40" y="169">출생</text><text x="126" y="169">1주</text><text x="214" y="169">2주</text><text x="302" y="169">3주</text><text x="385" y="169">현재</text></g><text x="370" y="{growth_label_y}" fill="#6374DC" font-size="11" font-weight="700">{current_weight:.1f}kg</text></svg></div><div class="home-card"><div class="home-title">키 성장</div><div class="home-label">같은 성별·월령 기준과 비교한 참고 그래프</div><svg class="growth-chart" viewBox="0 0 430 180"><path d="M42 32H410 M42 72H410 M42 112H410 M42 145H410" stroke="#E3E7F1" stroke-dasharray="3 3"/><path d="M52 119 L140 110 L228 100 L316 91 L402 {height_y:.1f}" fill="none" stroke="#20A26B" stroke-width="3"/><g fill="#20A26B"><circle cx="52" cy="119" r="4"/><circle cx="140" cy="110" r="4"/><circle cx="228" cy="100" r="4"/><circle cx="316" cy="91" r="4"/><circle cx="402" cy="{height_y:.1f}" r="4"/></g><g fill="#778198" font-size="11"><text x="0" y="36">60cm</text><text x="0" y="76">55cm</text><text x="0" y="116">50cm</text><text x="40" y="169">출생</text><text x="126" y="169">1주</text><text x="214" y="169">2주</text><text x="302" y="169">3주</text><text x="385" y="169">현재</text></g><text x="363" y="{height_label_y:.1f}" fill="#20A26B" font-size="11" font-weight="700">{current_height:.1f}cm</text></svg></div>''',
            unsafe_allow_html=True,
        )
    with assistant_column:
        st.markdown(
            f'''<div class="home-card"><div class="home-title">다음 예방접종</div><span class="vaccine-date">{vaccine['date']}</span> <b>{vaccine['name']}</b><div class="home-sub" style="margin:8px 0 0">접종 예정일까지 {vaccine['remaining']}</div></div>''',
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            st.markdown("<div class='section-title'>AI 육아 도우미</div>", unsafe_allow_html=True)
            st.markdown("<div class='muted'>서아의 월령과 최근 기록을 반영해 답변해 드려요.</div>", unsafe_allow_html=True)
            button_columns = st.columns(2)
            for column, (label, topic) in zip(button_columns * 2, (("◌ AI에 질문하기", ""), ("🍼 월령별 수유", "feeding"), ("🏥 주변 소아과", "hospital"), ("🛡️ 아기 안전 수칙", "safety"))):
                if column.button(label, key=f"home_assistant_{topic or 'chat'}", use_container_width=True):
                    st.session_state.selected_menu = "AI 육아 도우미"
                    st.session_state.chat_topic = topic
                    st.session_state.applied_chat_topic = ""
                    st.rerun()
