from __future__ import annotations

import streamlit as st

import api


def render_content() -> None:
    data = api.get_vaccinations(st.session_state.baby_id)["data"]
    next_item = data["next"]
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.markdown(f"<div class='soft-panel'><b>다음 예방접종 · {next_item['name']}</b><br><span class='muted'>{next_item['period']}</span><span style='float:right; color:#6577DD; font-weight:800'>{next_item['date']}</span></div>", unsafe_allow_html=True)
    st.markdown("<br><div class='section-title'>접종 내역 및 일정</div>", unsafe_allow_html=True)
    for name, period, status, state in data["items"]:
        icon = "✓" if state == "done" else "◷" if state == "soon" else "▣"
        color = "#20A26B" if state == "done" else "#DC7B23" if state == "soon" else "#6577DD"
        st.markdown(f"<div class='record-row'><span style='color:{color};font-weight:800'>{icon}</span>&nbsp;&nbsp;<span class='record-name'>{name}</span><br><span class='record-detail'>&nbsp;&nbsp;&nbsp;&nbsp;{period}</span><span style='float:right;color:{color};font-size:.78rem;font-weight:700'>{status}</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='notice'>프로토타입에서는 예방접종 정보가 가짜 데이터로 제공됩니다.</div></div>", unsafe_allow_html=True)


def render() -> None:
    render_content()

