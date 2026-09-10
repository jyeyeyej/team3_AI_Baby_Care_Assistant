from __future__ import annotations

from pathlib import Path

import streamlit as st

import api


def render() -> None:
    left, right = st.columns([1.05, 2.1], gap="large")
    with left:
        st.markdown("<br>", unsafe_allow_html=True)
        st.image(Path(__file__).resolve().parents[1] / "assets" / "bebeon-logo.png", width=260)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("## 반가워요 👋")
        st.caption("AI 육아 도우미를 시작해 보세요.")
        test_users = {
            "태경 보호자 김서아님": "user-001",
            "민준 보호자 한태경님": "user-002",
        }
        selected = st.selectbox("테스트 사용자", list(test_users))
        if st.button("로그인", use_container_width=True, type="primary"):
            result = api.test_login(test_users[selected])
            if result["success"]:
                st.session_state.logged_in = True
                st.session_state.user_id = result["data"]["user_id"]
                st.session_state.baby_id = result["data"]["baby_id"]
                st.session_state.session_id = result["data"]["session_id"]
                st.rerun()
            else:
                st.error(result.get("message", "로그인 세션을 만들지 못했습니다."))
        st.markdown("<br><br><br>", unsafe_allow_html=True)

    with right:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.caption("✣ 0–36개월 맞춤형 육아 도우미")
        st.markdown("<style>.login-headline{font-size:2.5rem;font-weight:800;line-height:1.15;margin:1rem 0}.login-headline .accent{color:#6577DD;font-size:1em;font-weight:900}@media(max-width:700px){.login-headline{font-size:2rem;white-space:nowrap}.login-headline .accent{white-space:normal}}</style><div class='login-headline'>우리 아기 맞춤<br><span class='accent'>육아 도우미 AI</span></div>", unsafe_allow_html=True)
        st.markdown("수유·수면·배변·성장 기록부터 월령별 육아 정보, 예방접종 일정, 주변 의료기관까지.<br>AI가 우리 아기에게 필요한 정보를 알려드려요.", unsafe_allow_html=True)
        st.markdown("<div style='font-size:1.05rem;font-weight:800;margin:1.7rem 0 .7rem;color:#202737'>주요 기능</div>", unsafe_allow_html=True)
        st.markdown("✓ 알림과 버튼으로 간편하게 기록  ")
        st.markdown("✓ 아기 정보와 알레르기를 반영한 답변  ")
        st.markdown("✓ 공식 자료를 바탕으로 한 육아 안내")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<div class='panel'><b>👶 태경이의 오늘</b><br><span class='muted'>생후 31일 · 분유 수유</span><br><br><div class='soft-panel'>🍼 마지막 수유 후 3시간이 지났어요<br><span class='muted'>태경이의 배고픔 신호를 확인해 주세요.</span></div></div>", unsafe_allow_html=True)
