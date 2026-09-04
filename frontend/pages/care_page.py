from __future__ import annotations

import streamlit as st

import api
from common import metric_card, render_page_header
from pages import vaccination_page


def _render_records() -> None:
    records = api.get_care_records(st.session_state.baby_id)["data"]
    grid = st.columns(2)
    with grid[0]: metric_card("최근 7일 수유", "47", "회")
    with grid[1]: metric_card("평균 수유량", "96", "ml")
    with grid[0]: metric_card("하루 평균 수면", "14.2", "시간")
    with grid[1]: metric_card("최근 7일 배변", "19", "회")
    st.markdown("<br><div class='panel'><div class='section-title'>최근 기록</div>", unsafe_allow_html=True)
    filters = st.radio("기록 필터", ["전체", "수유", "수면", "배변", "성장"], horizontal=True, label_visibility="collapsed")
    for record in records:
        st.markdown(f"<div class='record-row'><span class='record-time'>{record['time']}</span>&nbsp;&nbsp; {record['icon']} <span class='record-name'>{record['title']}</span><br><span class='record-detail'>{record['detail']}</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='notice'>수정·삭제는 보호자가 최종 확인한 뒤 반영됩니다.</div></div>", unsafe_allow_html=True)


def _render_pattern() -> None:
    pattern = api.get_care_pattern(st.session_state.baby_id)["data"]
    grid = st.columns(2)
    with grid[0]: metric_card("평균 수유 간격", pattern["average_interval"])
    with grid[1]: metric_card("1일 평균 수유", pattern["daily_feeding"], "회")
    with grid[0]: metric_card("평균 수면", pattern["daily_sleep"])
    with grid[1]: metric_card("1일 평균 배변", pattern["daily_diaper"], "회")
    st.markdown("<br><div class='panel'><div class='section-title'>최근 7일 수유 간격</div>", unsafe_allow_html=True)
    st.line_chart({"서아의 기록": pattern["intervals"], "현재 알림 간격 3시간": [3] * 7}, height=250)
    st.markdown("</div><br><div class='panel'><div class='section-title'>AI 패턴 요약</div>", unsafe_allow_html=True)
    st.markdown("<div class='notice'>💡 <b>수유 간격</b><br>최근 기록은 평균 3시간 12분 간격이에요. 현재 3시간 알림을 유지해도 좋아요.</div><br>", unsafe_allow_html=True)
    st.markdown("<div class='notice'>🌙 <b>수면 기록</b><br>수면 기록이 3일째예요. 규칙적인 기록이 조금 더 필요해요.</div><br>", unsafe_allow_html=True)
    st.markdown("<div class='notice'><b>안내</b><br>이 요약은 기록 패턴 분석이며 의학적 판단이나 진단이 아닙니다.</div></div>", unsafe_allow_html=True)


def _render_growth() -> None:
    growth = api.get_growth(st.session_state.baby_id)["data"]
    st.markdown("<div class='panel'><div class='section-title'>몸무게 변화</div>", unsafe_allow_html=True)
    selected = st.radio("성장 항목", ["몸무게", "키", "머리둘레"], horizontal=True, label_visibility="collapsed")
    key = {"몸무게": "weight", "키": "height", "머리둘레": "head"}[selected]
    st.line_chart({"서아": growth[key], "같은 성별·월령 참고 범위": growth["reference"]}, height=270)
    st.markdown("</div><br><div class='panel'><div class='section-title'>최근 측정 결과</div>", unsafe_allow_html=True)
    unit = {"몸무게": "kg", "키": "cm", "머리둘레": "cm"}[selected]
    st.markdown(f"<div class='notice'><b>현재 {selected} 4.2{unit}</b><br>같은 성별·월령 성장 참고자료에서 약 45백분위에 해당해요.</div><br>", unsafe_allow_html=True)
    st.markdown("<div class='notice'><b>성장 추세</b><br>출생 시 3.2kg에서 최근까지 꾸준히 증가하는 흐름이에요.</div><br>", unsafe_allow_html=True)
    st.markdown("<div class='notice'><b>참고해 주세요</b><br>백분위는 참고값이며 정상·비정상을 단정하지 않습니다.</div></div>", unsafe_allow_html=True)


def render() -> None:
    baby = api.get_baby(st.session_state.baby_id)["data"]
    render_page_header("육아 관리", "기록부터 성장·예방접종까지 한눈에 확인해요.", baby)
    tabs = st.tabs(["육아 기록", "생활 패턴", "성장", "예방접종"])
    with tabs[0]: _render_records()
    with tabs[1]: _render_pattern()
    with tabs[2]: _render_growth()
    with tabs[3]: vaccination_page.render_content()

