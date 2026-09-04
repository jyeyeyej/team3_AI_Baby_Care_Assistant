from __future__ import annotations

from datetime import date

import streamlit as st


COLORS = {
    "primary": "#6577DD",
    "primary_soft": "#EEF0FF",
    "canvas": "#F7F8FC",
    "border": "#E2E6F2",
    "text": "#1E2533",
    "muted": "#73809A",
    "card": "#FFFFFF",
}


def init_session() -> None:
    defaults = {
        "logged_in": False,
        "user_id": None,
        "baby_id": None,
        "session_id": None,
        "selected_menu": "홈",
        "care_tab": "육아 기록",
        "profile_tab": "아기 정보",
        "chat_messages": [],
        "pending_stt_tool_call_id": None,
        "request_in_progress": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def apply_style() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #F7F8FC; color: #1E2533; }
        #MainMenu, footer, header { visibility: hidden; }
        .block-container { max-width: 1200px; padding: 1.0rem 1.4rem 2rem; }
        [data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E2E6F2; }
        [data-testid="stSidebar"] > div:first-child { padding-top: 1.1rem; }
        .brand { font-weight: 800; font-size: 1.05rem; margin: .25rem 0 1.6rem; }
        .page-title { font-size: 1.7rem; font-weight: 800; margin: 0; }
        .page-subtitle { color: #73809A; margin: .18rem 0 1.25rem; font-size: .92rem; }
        .baby-badge { background: #FFFFFF; border: 1px solid #E2E6F2; border-radius: 999px;
            padding: .52rem .8rem; font-weight: 700; font-size: .84rem; text-align:center; }
        .panel { background: #FFFFFF; border: 1px solid #E2E6F2; border-radius: 18px; padding: 1.1rem; }
        .soft-panel { background: #EEF0FF; border: 1px solid #CBD3FF; border-radius: 17px; padding: 1rem 1.15rem; }
        .metric-card { background: #FFFFFF; border: 1px solid #E2E6F2; border-radius: 15px; padding: .92rem 1rem; min-height: 84px; }
        .metric-label { color: #73809A; font-size: .78rem; margin-bottom: .38rem; }
        .metric-value { color: #182131; font-weight: 800; font-size: 1.25rem; }
        .metric-unit { color: #6577DD; font-size: .8rem; font-weight: 700; }
        .section-title { font-size: 1.08rem; font-weight: 800; margin: 0 0 .8rem; }
        .muted { color: #73809A; font-size: .82rem; }
        .notice { background:#F0F2FF; color:#64718C; border-radius:10px; padding:.68rem .8rem; font-size:.78rem; }
        .chat-ai { background:#F0F2F8; border-radius:12px; padding:.75rem .85rem; margin:.5rem 2rem .5rem 0; font-size:.9rem; }
        .chat-user { background:#6577DD; color:#FFF; border-radius:12px; padding:.75rem .85rem; margin:.5rem 0 .5rem 2rem; font-size:.9rem; }
        .record-row { border: 1px solid #E2E6F2; border-radius: 13px; padding: .7rem .8rem; margin: .48rem 0; }
        .record-time { color:#73809A; font-size:.77rem; }
        .record-name { font-weight:800; font-size:.9rem; }
        .record-detail { color:#6577A0; font-size:.76rem; }
        div[data-testid="stButton"] > button { border-radius: 9px; border-color: #DDE2F2; font-weight: 650; }
        div[data-testid="stButton"] > button[kind="primary"] { background:#6577DD; border-color:#6577DD; }
        .stTabs [data-baseweb="tab-list"] { gap: .3rem; background:#EEF0FF; padding:.25rem; border-radius:11px; }
        .stTabs [data-baseweb="tab"] { flex:1; justify-content:center; border-radius:8px; height:38px; }
        .stTabs [aria-selected="true"] { background:#FFF; box-shadow:0 1px 4px #DCE0EE; }
        .stTabs [data-baseweb="tab-highlight"] { display:none; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def baby_age_days(birth_date: str) -> int:
    return (date.today() - date.fromisoformat(birth_date)).days


def render_baby_badge(baby: dict) -> None:
    st.markdown(
        f'<div class="baby-badge">👶 {baby["baby_name"]} · 생후 {baby["age_days"]}일</div>',
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str, baby: dict) -> None:
    left, right = st.columns([5, 1.45], vertical_alignment="center")
    with left:
        st.markdown(f'<div class="page-title">{title}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="page-subtitle">{subtitle}</div>', unsafe_allow_html=True)
    with right:
        render_baby_badge(baby)


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown('<div class="brand">🫧&nbsp; Baby Care</div>', unsafe_allow_html=True)
        menu_items = ["홈", "AI 육아 도우미", "육아 관리", "내 정보"]
        icons = {"홈": "⌂", "AI 육아 도우미": "◌", "육아 관리": "▥", "내 정보": "♙"}
        for item in menu_items:
            if st.button(f"{icons[item]}  {item}", key=f"menu_{item}", use_container_width=True,
                         type="primary" if st.session_state.selected_menu == item else "secondary"):
                st.session_state.selected_menu = item
                st.rerun()

        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.caption("이 프로젝트는 실제 인증 없이 준비된 가짜 사용자 데이터로 시연됩니다.")
    return st.session_state.selected_menu


def render_feeding_reminder(reminder: dict) -> None:
    st.markdown('<div class="soft-panel">', unsafe_allow_html=True)
    top, actions = st.columns([2.2, 1.35], vertical_alignment="center")
    with top:
        st.markdown("**🍼 마지막 수유 후 3시간이 지났어요**")
        st.caption("서아의 배고픔 신호를 확인해 주세요.")
    with actions:
        a, b, c = st.columns(3)
        if a.button("수유했어요", key="feed_now", type="primary"):
            st.session_state.selected_menu = "육아 관리"
            st.session_state.care_tab = "육아 기록"
            st.toast("육아 기록에서 수유 내용을 입력해 주세요.")
        if b.button("10분 후", key="feed_snooze"):
            st.toast("10분 후 다시 알려드릴게요.")
        if c.button("건너뛰기", key="feed_skip"):
            st.toast("설정한 간격 후 다시 알려드릴게요.")
    st.markdown("</div>", unsafe_allow_html=True)


def metric_card(label: str, value: str, unit: str = "") -> None:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value} <span class="metric-unit">{unit}</span></div></div>',
        unsafe_allow_html=True,
    )

