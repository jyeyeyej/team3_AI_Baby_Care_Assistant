from __future__ import annotations

import streamlit as st

from common import apply_style, init_session, render_sidebar
from pages import care_page, chat_page, home_page, login_page, profile_page


st.set_page_config(page_title="Baby Care", page_icon="👶", layout="wide")
init_session()
apply_style()

if not st.session_state.logged_in:
    login_page.render()
else:
    menu = render_sidebar()
    if menu == "홈":
        home_page.render()
    elif menu == "AI 육아 도우미":
        chat_page.render()
    elif menu == "육아 관리":
        care_page.render()
    elif menu == "내 정보":
        profile_page.render()
