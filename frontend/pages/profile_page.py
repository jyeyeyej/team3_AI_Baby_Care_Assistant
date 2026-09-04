from __future__ import annotations

import streamlit as st

import api
from common import render_page_header


def render() -> None:
    baby = api.get_baby(st.session_state.baby_id)["data"]
    render_page_header("내 정보", "보호자 정보와 AI 답변에 반영할 아기 정보를 관리해요.", baby)
    st.markdown(f"<div class='panel'>👶 <b>{baby['baby_name']} · 생후 {baby['age_days']}일</b><br><span class='muted'>{baby['birth_date']} 출생 · {baby['gender']} · {baby['feeding_type']} 수유</span></div><br>", unsafe_allow_html=True)
    tabs = st.tabs(["아기 정보", "보호자 정보", "알림 설정"])
    with tabs[0]:
        st.markdown("<div class='panel'><div class='section-title'>기본 정보</div><span class='muted'>월령 계산과 맞춤형 육아 안내에 사용됩니다.</span>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: st.text_input("아기 이름", baby["baby_name"])
        with c2: st.text_input("생년월일", baby["birth_date"])
        with c1: st.selectbox("성별", [baby["gender"], "남아"])
        with c2: st.selectbox("수유 방식", [baby["feeding_type"], "모유", "혼합"])
        st.markdown("<br><div class='section-title'>성장 정보</div>", unsafe_allow_html=True)
        with c1: st.text_input("출생 몸무게", f"{baby['birth_weight_kg']} kg")
        with c2: st.text_input("현재 몸무게", f"{baby['current_weight_kg']} kg")
        with c1: st.text_input("현재 키", f"{baby['current_height_cm']} cm")
        with c2: st.text_input("머리둘레", f"{baby['head_circumference_cm']} cm")
        st.markdown("<br><div class='section-title'>중요 건강정보</div>", unsafe_allow_html=True)
        st.text_input("음식·약물 알레르기", ", ".join(baby["allergies"]))
        st.caption("현재 알림·과거 병력·복용약은 이 텍스트 입력에서 제외되어 있어요.")
        st.button("변경사항 저장", type="primary")
        st.markdown("</div>", unsafe_allow_html=True)
    with tabs[1]:
        st.markdown("<div class='panel'><div class='section-title'>보호자 정보</div><p class='muted'>테스트 사용자 정보는 읽기 전용입니다.</p><b>서아 보호자</b></div>", unsafe_allow_html=True)
    with tabs[2]:
        st.markdown("<div class='panel'><div class='section-title'>수유 알림 간격</div>", unsafe_allow_html=True)
        st.radio("간격", ["2시간", "2시간 30분", "3시간", "3시간 30분"], horizontal=True, index=2)
        st.button("알림 설정 저장", type="primary")
        st.markdown("</div>", unsafe_allow_html=True)

