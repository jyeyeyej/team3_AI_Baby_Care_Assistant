from __future__ import annotations

import streamlit as st

import api
from common import render_feeding_reminder


def _send(message: str) -> None:
    st.session_state.chat_messages.append(("user", message))
    answer = api.send_chat(message)["data"]
    st.session_state.chat_messages.append(("ai", answer["answer"]))


def render() -> None:
    baby = api.get_baby(st.session_state.baby_id)["data"]
    st.markdown(f"<div class='page-title'>{baby['baby_name']}의 AI 육아 도우미</div><div class='page-subtitle'>생후 {baby['age_days']}일 · {baby['current_weight_kg']}kg · {baby['feeding_type']} 수유</div>", unsafe_allow_html=True)
    render_feeding_reminder({})
    st.markdown("<br><div class='panel'>", unsafe_allow_html=True)
    if not st.session_state.chat_messages:
        st.markdown("<div class='chat-ai'>안녕하세요! 서아는 오늘 생후 30일이에요. 수유·수면·배변을 간단히 기록하거나, 월령에 맞는 육아 정보를 물어보세요.</div>", unsafe_allow_html=True)
        st.markdown("<div class='chat-user'>생후 30일 아기는 분유를 얼마나 먹나요?</div>", unsafe_allow_html=True)
        st.markdown("<div class='chat-ai'>생후 30일 아기의 수유량은 아기마다 달라요. 서아의 최근 수유와 배고픔 신호를 함께 보세요.</div>", unsafe_allow_html=True)
    else:
        for sender, message in st.session_state.chat_messages:
            css = "chat-user" if sender == "user" else "chat-ai"
            st.markdown(f"<div class='{css}'>{message}</div>", unsafe_allow_html=True)
    chips = st.columns(4)
    for column, label in zip(chips, ["🍼 월령별 수유", "▣ 기저귀 사진 분석", "🏥 주변 소아과", "🍚 이유식 궁금증"]):
        if column.button(label, use_container_width=True):
            _send(label)
            st.rerun()
    prompt = st.chat_input("육아 기록이나 궁금한 점을 입력하세요")
    if prompt:
        _send(prompt)
        st.rerun()
    st.markdown("</div><br>", unsafe_allow_html=True)
    left, right = st.columns([1, 1.35])
    with left:
        st.markdown("<div class='panel'><div class='section-title'>빠른 기록</div>", unsafe_allow_html=True)
        st.columns(3)[0].button("🍼 수유")
        st.columns(3)[1].button("🌙 수면")
        st.columns(3)[2].button("💩 배변")
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown(f"<div class='panel'><div class='section-title'>AI가 참고 중인 정보</div><span class='muted'>월령</span><b style='float:right'>생후 {baby['age_days']}일</b><br><span class='muted'>몸무게</span><b style='float:right'>{baby['current_weight_kg']}kg</b><br><span class='muted'>수유 방식</span><b style='float:right'>{baby['feeding_type']}</b><br><span class='muted'>특이사항</span><b style='float:right'>{', '.join(baby['allergies'])} 알레르기</b></div>", unsafe_allow_html=True)

