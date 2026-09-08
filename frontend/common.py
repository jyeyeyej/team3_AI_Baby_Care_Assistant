from __future__ import annotations

from datetime import date

import streamlit as st

import api


COLORS = {
    "primary": "#6374DC",
    "primary_soft": "#EEF1FF",
    "canvas": "#F8F9FC",
    "border": "#E3E7F1",
    "text": "#202737",
    "muted": "#778198",
    "card": "#FFFFFF",
}

MENU_ITEMS = ("홈", "AI 육아 도우미", "육아 관리", "내 정보")


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
        "chat_topic": "",
        "applied_chat_topic": "",
        "last_navigation_query": None,
        "pending_notice": "",
        "editing_record_index": None,
        "pending_stt_tool_call_id": None,
        "chat_draft": "",
        "chat_draft_nonce": 0,
        "pending_chat_message": "",
        "last_chat_submission": "",
        "voice_transcript": "",
        "last_voice_audio_signature": "",
        "pending_stt_record": None,
        "voice_recording_counter": 0,
        "show_feeding_amount_options": False,
        "feeding_save_message": "",
        "feeding_interval_minutes": 180,
        "feeding_reminder_status": "active",
        "feeding_snooze_until": None,
        "show_hospital_search": False,
        "diaper_analysis_result": None,
        "last_diaper_signature": "",
        "request_in_progress": False,
        "quick_record_type": None,
        "quick_record_notice": "",
        "navigation_restored": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def restore_navigation_from_url() -> None:
    """새 Streamlit 세션에서도 테스트 로그인과 현재 메뉴를 복원한다."""
    params = st.query_params
    page = params.get("page")
    topic = params.get("topic")
    notice = params.get("notice")
    query_signature = (params.get("demo"), page, topic, notice)

    # 메뉴 버튼을 눌러 발생한 rerun에서는 이전 URL로 화면을 되돌리지 않는다.
    # 홈의 HTML 바로가기처럼 URL이 실제로 바뀐 경우에만 메뉴와 주제를 반영한다.
    if st.session_state.last_navigation_query != query_signature:
        if page in MENU_ITEMS:
            st.session_state.selected_menu = page
        if topic == "chat":
            st.session_state.chat_topic = ""
            st.session_state.applied_chat_topic = ""
        elif topic in {"feeding", "sleep", "hospital", "weaning", "diaper", "safety"}:
            st.session_state.chat_topic = topic
        if notice in {"snooze", "skip"}:
            st.session_state.pending_notice = notice
        st.session_state.last_navigation_query = query_signature

    st.session_state.navigation_restored = True


def persist_navigation_to_url() -> None:
    """현재 화면을 URL에 기록해 브라우저 새로고침 뒤에도 유지한다."""
    if not st.session_state.logged_in:
        return

    desired = {"page": st.session_state.selected_menu}
    if st.session_state.selected_menu == "AI 육아 도우미" and st.session_state.chat_topic:
        desired["topic"] = st.session_state.chat_topic
    if st.session_state.selected_menu == "육아 관리" and st.session_state.editing_record_index is not None:
        desired["edit_record"] = str(st.session_state.editing_record_index)
    current = st.query_params.to_dict()
    if current != desired:
        st.query_params.clear()
        st.query_params.update(desired)


def apply_style() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #F8F9FC; color: #202737; }
        #MainMenu, footer { visibility: hidden; }
        header { background: transparent !important; }
        header [data-testid="stDecoration"], header [data-testid="stStatusWidget"] { display: none !important; }
        /* 왼쪽 바를 접은 뒤에도 다시 열 수 있는 Streamlit 기본 버튼 */
        [data-testid="collapsedControl"],
        [data-testid="stExpandSidebarButton"],
        [data-testid="stSidebarCollapsedControl"],
        button[title="Open sidebar"],
        button[aria-label="Open sidebar"] {
            display: flex !important; visibility: visible !important;
            position: fixed !important; top: .65rem; left: .65rem; z-index: 1000;
            background: #FFFFFF !important; border: 1px solid #E3E7F1 !important;
            border-radius: 9px !important; box-shadow: 0 2px 8px rgba(54, 67, 106, .10);
        }
        .block-container, [data-testid="stMainBlockContainer"] { max-width: 1080px !important; padding: 1.6rem 1.35rem 2rem; margin: 0 auto; }
        [data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E3E7F1;
            min-width: 230px !important; max-width: 230px !important; }
        [data-testid="stSidebar"] > div:first-child { min-width: 230px !important; max-width: 230px !important; }
        [data-testid="stSidebar"] > div:first-child { padding-top: 1.1rem; }
        /* pages/ 폴더에서 Streamlit이 자동 생성하는 메뉴는 사용하지 않습니다. */
        [data-testid="stSidebarNav"] { display: none; }
        .brand { font-weight: 800; font-size: 1.05rem; margin: .25rem 0 1.6rem; }
        .sidebar-baby-card { background:#F7F8FC; border:1px solid #E3E7F1; border-radius:12px;
            padding:.7rem; color:#202737; }
        .sidebar-baby-name { font-size:.84rem; font-weight:800; }
        .sidebar-baby-age { color:#778198; font-size:.72rem; margin-top:.12rem; }
        .sidebar-menu-link, .sidebar-menu-link:link, .sidebar-menu-link:visited { display:block; text-decoration:none!important;
            color:#202737; background:#FFFFFF; border:1px solid #DFE4F1; border-radius:9px; padding:.62rem .75rem;
            margin:.34rem 0; text-align:center; font-size:.92rem; font-weight:650; }
        .sidebar-menu-link.active { color:#FFFFFF; background:#6374DC; border-color:#6374DC; }
        .page-title { font-size: 1.7rem; font-weight: 800; margin: 0; }
        .page-subtitle { color: #778198; margin: .18rem 0 1.25rem; font-size: .92rem; }
        .baby-badge { background: #FFFFFF; border: 1px solid #E3E7F1; border-radius: 999px;
            padding: .52rem .8rem; font-weight: 700; font-size: .84rem; text-align:center; }
        .panel { background: #FFFFFF; border: 1px solid #E3E7F1; border-radius: 18px; padding: 1.1rem; }
        .soft-panel { background: #EEF1FF; border: 1px solid #CBD3FF; border-radius: 17px; padding: 1rem 1.15rem; }
        .metric-card { background: #F7F8FC; border: 0; border-radius: 11px; padding: .92rem 1rem; min-height: 84px; }
        .metric-label { color: #778198; font-size: .78rem; margin-bottom: .38rem; }
        .metric-value { color: #182131; font-weight: 800; font-size: 1.25rem; }
        .metric-unit { color: #6374DC; font-size: .8rem; font-weight: 700; }
        .section-title { font-size: 1.08rem; font-weight: 800; margin: 0 0 .8rem; }
        .muted { color: #778198; font-size: .9rem; }
        .notice { background:#EEF1FF; color:#68758E; border-radius:10px; padding:.68rem .8rem; font-size:.84rem; }
        small { font-size: .78rem !important; }
        .chat-ai { background:#F1F3F8; border-radius:12px; padding:.75rem .85rem; margin:.5rem 2rem .5rem 0; font-size:.9rem; }
        .chat-user { background:#6374DC; color:#FFF; border-radius:12px; padding:.75rem .85rem; margin:.5rem 0 .5rem 2rem; font-size:.9rem; }
        .record-row { border: 1px solid #E3E7F1; border-radius: 13px; padding: .7rem .8rem; margin: .48rem 0; }
        .record-time { color:#778198; font-size:.77rem; }
        .record-name { font-weight:800; font-size:.9rem; }
        .record-detail { color:#6577A0; font-size:.76rem; }
        div[data-testid="stButton"] > button { background:#FFFFFF; border-radius: 9px; border-color: #DFE4F1; font-weight: 650; }
        div[data-testid="stButton"] > button[kind="primary"] { background:#6374DC; border-color:#6374DC; color:#FFFFFF; }
        div[data-baseweb="input"] > div, div[data-baseweb="select"] > div { background:#F6F7FB; border-color:#DFE4F1; }
        .stTabs [data-baseweb="tab-list"] { gap:0; background:#EEF1FF; padding:.28rem; border-radius:11px; }
        .stTabs [data-baseweb="tab"] { flex:1; justify-content:center; border-radius:8px; height:39px;
            color:#69758D; font-size:.84rem; }
        .stTabs [aria-selected="true"] { background:#FFF; color:#6374DC; box-shadow:0 1px 5px #DCE0EE; }
        .stTabs [data-baseweb="tab-highlight"] { display:none; }
        /* Streamlit 카드 컨테이너의 실제 내부 요소까지 흰색으로 고정 */
        [data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stVerticalBlockBorderWrapper"] > div,
        [data-testid="stVerticalBlockBorderWrapper"] > div > div,
        div.stVerticalBlock.st-emotion-cache-1te8eqs {
            background-color: #FFFFFF !important;
            border-radius: 18px;
            border-color: #E3E7F1;
        }
        /* 지표 안쪽 박스는 시안의 아주 연한 회청색 */
        [data-testid="stVerticalBlockBorderWrapper"] .metric-card {
            background-color: #F4F6FB !important;
        }
        div.stVerticalBlock.st-emotion-cache-1te8eqs.st-key-feeding_card {
            background-color: #EEF1FF !important;
            border-color: #C9D2FF !important;
        }
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
        icons = {"홈": "🏠", "AI 육아 도우미": "🤖", "육아 관리": "🍼", "내 정보": "👤"}
        for item in menu_items:
            if st.button(
                f"{icons[item]}  {item}",
                key=f"menu_{item}",
                use_container_width=True,
                type="primary" if st.session_state.selected_menu == item else "secondary",
            ):
                st.session_state.selected_menu = item
                st.rerun()

        st.markdown("<br><br><br>", unsafe_allow_html=True)
        baby_result = api.get_baby(
            st.session_state.baby_id,
            user_id=st.session_state.user_id,
            session_id=st.session_state.session_id,
        )
        baby = baby_result.get("data", {}) if baby_result.get("success") else {}
        baby_name = baby.get("baby_name", "아기")
        birth_date = str(baby.get("birth_date", ""))
        birthday_label = f"생일 {birth_date}" if birth_date else "생일 정보 없음"
        st.markdown(
            "<div class='sidebar-baby-card'>"
            "<span style='font-size:1.35rem'>👶</span> "
            f"<span class='sidebar-baby-name'>{baby_name}</span>"
            f"<div class='sidebar-baby-age'>{birthday_label}</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    return st.session_state.selected_menu


def render_feeding_reminder(reminder: dict) -> None:
    st.markdown(
        """
        <style>
        .assistant-reminder{background:#EEF1FF;border:1px solid #C9D2FF;border-radius:15px;padding:18px 20px;margin:12px 0 16px;display:flex;justify-content:space-between;align-items:center}.assistant-reminder b{font-size:16px}.assistant-reminder-sub{font-size:14px;color:#778198;margin-top:4px}.assistant-reminder-btn,.assistant-reminder-btn:link,.assistant-reminder-btn:visited{display:inline-block;text-decoration:none!important;color:#202737;background:#fff;border:1px solid #DFE4F1;border-radius:8px;padding:8px 11px;margin-left:5px;font-size:13px}.assistant-reminder-btn.primary{background:#6374DC;color:#fff;border-color:#6374DC;font-weight:700}@media(max-width:700px){.assistant-reminder{align-items:flex-start;gap:12px;flex-direction:column}.assistant-reminder-btn{margin-left:0!important;margin-right:5px}}
        </style>
        <div class="assistant-reminder"><div><b>🍼 마지막 수유 후 3시간이 지났어요</b><div class="assistant-reminder-sub">서아의 배고픔 신호를 확인해 주세요.</div></div><div><a class="assistant-reminder-btn primary" target="_self" href="?demo=1&amp;page=%EC%9C%A1%EC%95%84%20%EA%B4%80%EB%A6%AC">수유했어요</a><a class="assistant-reminder-btn" target="_self" href="?demo=1&amp;page=AI%20%EC%9C%A1%EC%95%84%20%EB%8F%84%EC%9A%B0%EB%AF%B8&amp;notice=snooze">10분 후</a><a class="assistant-reminder-btn" target="_self" href="?demo=1&amp;page=AI%20%EC%9C%A1%EC%95%84%20%EB%8F%84%EC%9A%B0%EB%AF%B8&amp;notice=skip">건너뛰기</a></div></div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, unit: str = "") -> None:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value} <span class="metric-unit">{unit}</span></div></div>',
        unsafe_allow_html=True,
    )
