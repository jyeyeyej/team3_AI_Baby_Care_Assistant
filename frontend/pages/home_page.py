from __future__ import annotations

import streamlit as st

import api
from common import metric_card, render_feeding_reminder, render_page_header


def render() -> None:
    baby = api.get_baby(st.session_state.baby_id)["data"]
    dashboard = api.get_dashboard(st.session_state.baby_id)["data"]
    render_page_header(f"안녕하세요, {baby['baby_name']} 보호자님 👋", f"{baby['baby_name']}는 오늘 생후 {baby['age_days']}일이에요.", baby)
    render_feeding_reminder({})
    st.markdown("<br>", unsafe_allow_html=True)

    left, right = st.columns([1.45, 1], gap="medium")
    with left:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        title, link = st.columns([3, 1])
        title.markdown("<div class='section-title'>최근 7일 육아 기록</div>", unsafe_allow_html=True)
        if link.button("AI로 기록하기", key="home_quick_log"):
            st.session_state.selected_menu = "AI 육아 도우미"
            st.rerun()
        cols = st.columns(3)
        with cols[0]: metric_card("수유", dashboard["feeding"]["average_count"], "하루 평균")
        with cols[1]: metric_card("수면", dashboard["sleep"]["daily_hours"], "하루 평균")
        with cols[2]: metric_card("배변", dashboard["diaper"]["daily_count"], "하루 평균")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<div class='panel'><div class='section-title'>몸무게 성장</div><span class='muted'>같은 성별·월령 기준과 비교한 참고 그래프</span>", unsafe_allow_html=True)
        st.line_chart({"서아": [3.2, 3.45, 3.7, 4.0, 4.2], "참고 범위": [3.45, 3.6, 3.85, 4.1, 4.35]}, height=210)
        st.markdown("<div class='notice'>한 번의 수치로 정상·비정상을 판단하지 않고 성장 추세를 확인해 주세요.</div></div>", unsafe_allow_html=True)

    with right:
        vaccine = dashboard["next_vaccination"]
        st.markdown("<div class='panel'><div class='section-title'>다음 예방<br>접종</div>", unsafe_allow_html=True)
        st.markdown(f"<b style='color:#6577DD'>{vaccine['date']}</b>&nbsp;&nbsp; <b>{vaccine['name']}</b><br><span class='muted'>접종 예정일까지 {vaccine['remaining']}</span><hr><div class='notice'>예방접종 정보는 테스트 데이터입니다.</div></div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<div class='panel'><div class='section-title'>AI 육아 도우미</div><span class='muted'>서아의 월령과 최근 기록을 반영해 답변해 드려요.</span></div>", unsafe_allow_html=True)
        a, b = st.columns(2)
        if a.button("수유 기록", use_container_width=True):
            st.session_state.selected_menu = "AI 육아 도우미"; st.rerun()
        if b.button("수면 기록", use_container_width=True):
            st.session_state.selected_menu = "AI 육아 도우미"; st.rerun()
        if st.button("소아과 찾기"):
            st.session_state.selected_menu = "AI 육아 도우미"; st.rerun()

