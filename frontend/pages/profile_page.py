from __future__ import annotations
import streamlit as st
import api
from common import render_page_header

def render() -> None:
    baby_data=api.get_baby(st.session_state.baby_id, user_id=st.session_state.user_id, session_id=st.session_state.session_id)["data"]
    st.session_state.setdefault("profile_values", baby_data.copy())
    st.session_state.setdefault("profile_editing", False)
    st.session_state.setdefault("guardian_values", {"name": "김서아", "relation": "엄마", "phone": "010-1234-5678", "email": "seoa.guardian@example.com"})
    st.session_state.setdefault("guardian_editing", False)
    b=st.session_state.profile_values
    render_page_header("내 정보","보호자 정보와 AI 답변에 반영할 아기 정보를 관리해요.",b)
    tab_labels = ["아기 정보", "보호자 정보", "알림 설정"]
    st.session_state.setdefault("profile_selected", "아기 정보")
    tab_columns = st.columns(3, gap="small")
    for column, label in zip(tab_columns, tab_labels):
        if column.button(
            label,
            key=f"profile_tab_{label}",
            use_container_width=True,
            type="primary" if st.session_state.profile_selected == label else "secondary",
        ):
            st.session_state.profile_selected = label
            st.rerun()
    selected = st.session_state.profile_selected
    if selected=="보호자 정보":
        guardian = st.session_state.guardian_values
        if st.button("✎ 수정하기", key="edit_guardian_profile", type="primary"):
            st.session_state.guardian_editing = True
        if st.session_state.guardian_editing:
            with st.form("guardian_profile_form"):
                st.markdown("#### 보호자 정보 수정")
                left, right = st.columns(2)
                name = left.text_input("보호자 이름", value=guardian["name"])
                relation = right.selectbox("아기와의 관계", ["엄마", "아빠", "보호자"], index=["엄마", "아빠", "보호자"].index(guardian["relation"]))
                phone = st.text_input("연락처", value=guardian["phone"])
                email = st.text_input("이메일", value=guardian["email"])
                save, cancel = st.columns(2)
                if save.form_submit_button("저장하기", type="primary", use_container_width=True):
                    st.session_state.guardian_values = {"name": name, "relation": relation, "phone": phone, "email": email}
                    st.session_state.guardian_editing = False
                    st.toast("보호자 정보를 저장했습니다.")
                    st.rerun()
                if cancel.form_submit_button("취소", use_container_width=True):
                    st.session_state.guardian_editing = False
                    st.rerun()
            return
        st.markdown(f"""
        <style>.guardian-card{{background:#fff;border:1px solid #E3E7F1;border-radius:14px;padding:16px}}.guardian-card h3{{margin:0 0 5px;font-size:18px}}.guardian-help{{font-size:13px;color:#778198;margin-bottom:14px}}.guardian-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.guardian-item{{background:#F4F6FB;border:1px solid #DFE4F1;border-radius:8px;padding:10px;font-size:13px;color:#778198}}.guardian-item b{{display:block;color:#202737;margin-top:5px}}@media(max-width:700px){{.guardian-grid{{grid-template-columns:1fr}}}}</style><div class='guardian-card'><h3>보호자 정보</h3><div class='guardian-help'>아기 생활 기록과 맞춤형 안내를 관리하는 보호자 정보입니다.</div><div class='guardian-grid'><div class='guardian-item'>보호자 이름<b>{guardian['name']}</b></div><div class='guardian-item'>아기와의 관계<b>{guardian['relation']}</b></div><div class='guardian-item'>연락처<b>{guardian['phone']}</b></div><div class='guardian-item'>이메일<b>{guardian['email']}</b></div></div></div>
        """, unsafe_allow_html=True); return
    if selected=="알림 설정":
        st.session_state.setdefault("feeding_interval_minutes", 180)
        st.session_state.setdefault("feeding_interval_choice", "3시간")
        minutes_by_choice = {"2시간 30분": 150, "3시간": 180, "3시간 30분": 210}
        st.markdown("<div style='background:#fff;border:1px solid #E3E7F1;border-radius:14px;padding:16px 16px 4px'><h3 style='margin:0 0 5px;font-size:18px'>수유 알림 설정</h3><p style='color:#778198;font-size:13px'>마지막 수유 시각을 기준으로 다음 알림을 알려드려요.</p></div>", unsafe_allow_html=True)
        st.markdown("<div style='background:#EEF1FF;border:1px solid #C9D2FF;border-radius:10px;padding:11px 13px;margin:8px 0 12px;font-size:14px'>현재 알림 간격 <b style='float:right'>" + (f"{st.session_state.feeding_interval_minutes // 60}시간 {st.session_state.feeding_interval_minutes % 60}분" if st.session_state.feeding_interval_minutes % 60 else f"{st.session_state.feeding_interval_minutes // 60}시간") + "</b></div>", unsafe_allow_html=True)
        choices = ["2시간 30분", "3시간", "3시간 30분", "직접 입력"]
        columns = st.columns(4, gap="small")
        for column, choice in zip(columns, choices):
            if column.button(choice, key=f"interval_{choice}", use_container_width=True, type="primary" if st.session_state.feeding_interval_choice == choice else "secondary"):
                st.session_state.feeding_interval_choice = choice
                if choice in minutes_by_choice:
                    st.session_state.feeding_interval_minutes = minutes_by_choice[choice]
                st.rerun()
        interval = st.session_state.feeding_interval_minutes
        if st.session_state.feeding_interval_choice == "직접 입력":
            interval = st.number_input("알림 간격 (분)", min_value=30, max_value=720, value=interval, step=30, help="30분부터 12시간(720분)까지 입력할 수 있어요.")
        if st.button("알림 설정 저장", key="save_reminder_setting", type="primary"):
            st.session_state.feeding_interval_minutes = interval
            st.toast("수유 알림 간격을 저장했습니다.")
        return
    if st.button("✎ 수정하기", key="edit_baby_profile", type="primary"):
        st.session_state.profile_editing = True
    if st.session_state.profile_editing:
        with st.form("baby_profile_form"):
            st.markdown("#### 아기 정보 수정")
            left, right = st.columns(2)
            name = left.text_input("아기 이름", value=b["baby_name"])
            birth_date = right.text_input("생년월일", value=b["birth_date"])
            left, right = st.columns(2)
            gender = left.selectbox("성별", ["여아", "남아"], index=0 if b["gender"] == "여아" else 1)
            feeding = right.selectbox("수유 방식", ["분유", "모유", "혼합"], index=["분유", "모유", "혼합"].index(b["feeding_type"]))
            left, right = st.columns(2)
            weight = left.number_input("현재 몸무게 (kg)", min_value=0.0, value=float(b["current_weight_kg"]), step=0.1)
            height = right.number_input("현재 키 (cm)", min_value=0.0, value=float(b["current_height_cm"]), step=0.1)
            allergies_text = st.text_input("음식·약물 알레르기", value=", ".join(b["allergies"]), placeholder="예: 땅콩, 계란")
            save, cancel = st.columns(2)
            if save.form_submit_button("저장하기", type="primary", use_container_width=True):
                allergies = [item.strip() for item in allergies_text.split(",") if item.strip()]
                st.session_state.profile_values.update({"baby_name": name, "birth_date": birth_date, "gender": gender, "feeding_type": feeding, "current_weight_kg": weight, "current_height_cm": height, "allergies": allergies})
                st.session_state.profile_editing = False
                st.toast("아기 정보가 저장되었습니다.")
                st.rerun()
            if cancel.form_submit_button("취소", use_container_width=True):
                st.session_state.profile_editing = False
                st.rerun()
        return
    st.markdown("<style>.boxx h4 span{display:none!important}</style>", unsafe_allow_html=True)
    st.markdown(f'''<style>.babyx,.boxx{{background:#fff;border:1px solid #E3E7F1;border-radius:14px;padding:14px;margin:9px 0}}.boxx h4{{margin:0 0 4px}}.boxx small{{color:#778198;font-size:13px}}.fields{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:12px}}.field{{font-size:13px;color:#778198}}.inputx{{background:#F4F6FB;border:1px solid #DFE4F1;border-radius:7px;color:#202737;padding:9px;margin-top:5px;font-size:13px}}.noticex{{background:#EEF1FF;border-radius:8px;color:#68758E;padding:9px;font-size:13px;margin-top:10px}}</style><div class='babyx'>👶　<b>{b['baby_name']} · 생후 {b['age_days']}일</b><br><small style='margin-left:25px;color:#778198'>{b['birth_date']} 출생 · {b['gender']} · {b['feeding_type']} 수유</small></div><div class='boxx'><h4>기본 정보 <span style='float:right;font-size:13px;border:1px solid #DFE4F1;padding:5px;border-radius:7px'>✎ 수정</span></h4><small>월령 계산과 맞춤형 육아 안내에 사용됩니다.</small><div class='fields'><div class='field'>아기 이름<div class='inputx'>{b['baby_name']}</div></div><div class='field'>생년월일<div class='inputx'>{b['birth_date']}</div></div><div class='field'>성별<div class='inputx'>{b['gender']}</div></div><div class='field'>수유 방식<div class='inputx'>{b['feeding_type']}</div></div></div></div><div class='boxx'><h4>성장 정보</h4><small>성장 곡선과 월령별 참고값 비교에 사용됩니다.</small><div class='fields'><div class='field'>출생 몸무게<div class='inputx'>{b['birth_weight_kg']} kg</div></div><div class='field'>현재 몸무게<div class='inputx'>{b['current_weight_kg']} kg</div></div><div class='field'>현재 키<div class='inputx'>{b['current_height_cm']} cm</div></div><div class='field'>머리둘레<div class='inputx'>{b['head_circumference_cm']} cm</div></div></div><div class='noticex'>성장 측정값은 ‘육아 관리’에서 새 기록을 추가하면 최신 값으로 갱신됩니다.</div></div><div class='boxx'><h4>중요 건강정보</h4><small>관련 육아 정보를 안내하기 전에 AI가 우선 확인합니다.</small><div class='field' style='margin-top:12px'>음식·약물 알레르기<div class='inputx'>⚠ {', '.join(b['allergies'])}</div></div></div>''',unsafe_allow_html=True)
