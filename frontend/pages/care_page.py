from __future__ import annotations
import streamlit as st
import api
from common import render_page_header

def render() -> None:
    baby=api.get_baby(st.session_state.baby_id, user_id=st.session_state.user_id, session_id=st.session_state.session_id)["data"]
    records=api.get_care_records(st.session_state.baby_id)["data"]
    st.session_state.setdefault("care_record_overrides", {})
    for index, override in st.session_state.care_record_overrides.items():
        records[index].update(override)
    render_page_header("육아 관리","기록부터 성장·예방접종까지 한눈에 확인해요.",baby)
    tab_labels = ["육아 기록", "생활 패턴", "성장", "예방접종"]
    st.session_state.setdefault("care_selected", "육아 기록")
    tab_columns = st.columns(4, gap="small")
    for column, label in zip(tab_columns, tab_labels):
        if column.button(
            label,
            key=f"care_tab_{label}",
            use_container_width=True,
            type="primary" if st.session_state.care_selected == label else "secondary",
        ):
            st.session_state.care_selected = label
            st.rerun()
    selected = st.session_state.care_selected
    st.markdown("<style>h3{font-size:18px!important}</style>", unsafe_allow_html=True)
    query_edit = st.query_params.get("edit_record")
    if query_edit is not None and query_edit.isdigit() and int(query_edit) < len(records):
        st.session_state.editing_record_index = int(query_edit)
    if selected=="생활 패턴":
        p=api.get_care_pattern(st.session_state.baby_id)["data"]
        st.markdown(f"""
        <div style='background:#fff;border:1px solid #E3E7F1;border-radius:15px;padding:16px'>
          <h3>생활 패턴</h3>
          <div style='display:grid;grid-template-columns:1fr 1fr;gap:10px'>
            <div style='background:#F4F6FB;padding:12px;border-radius:10px;color:#778198;font-size:13px'>평균 수유 간격<br><b style='color:#202737;font-size:17px'>{p['average_interval']}</b></div>
            <div style='background:#F4F6FB;padding:12px;border-radius:10px;color:#778198;font-size:13px'>1일 평균 수유<br><b style='color:#202737;font-size:17px'>{p['daily_feeding']}</b></div>
            <div style='background:#F4F6FB;padding:12px;border-radius:10px;color:#778198;font-size:13px'>평균 수면<br><b style='color:#202737;font-size:17px'>{p['daily_sleep']}</b></div>
            <div style='background:#F4F6FB;padding:12px;border-radius:10px;color:#778198;font-size:13px'>1일 평균 배변<br><b style='color:#202737;font-size:17px'>{p['daily_diaper']}</b></div>
          </div>
          <h4 style='margin:20px 0 6px'>최근 7일 수유 간격</h4>
          <svg viewBox='0 0 620 245' role='img' aria-label='최근 7일 수유 간격 그래프' style='width:100%;height:auto'>
            <path d='M55 38H590 M55 83H590 M55 128H590 M55 173H590' stroke='#E3E7F1' stroke-dasharray='4 4'/>
            <path d='M55 128H590' stroke='#F2A365' stroke-width='2' stroke-dasharray='6 5'/>
            <path d='M65 152 L150 130 L235 139 L320 102 L405 114 L490 82 L575 93' fill='none' stroke='#6374DC' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'/>
            <g fill='#6374DC'><circle cx='65' cy='152' r='4'/><circle cx='150' cy='130' r='4'/><circle cx='235' cy='139' r='4'/><circle cx='320' cy='102' r='4'/><circle cx='405' cy='114' r='4'/><circle cx='490' cy='82' r='4'/><circle cx='575' cy='93' r='4'/></g>
            <g fill='#778198' font-size='12'><text x='12' y='42'>5시간</text><text x='12' y='87'>4시간</text><text x='12' y='132'>3시간</text><text x='12' y='177'>2시간</text><text x='55' y='211'>월</text><text x='140' y='211'>화</text><text x='225' y='211'>수</text><text x='310' y='211'>목</text><text x='395' y='211'>금</text><text x='480' y='211'>토</text><text x='565' y='211'>일</text></g>
            <text x='477' y='121' fill='#E58B42' font-size='12'>평균 알림 간격 3시간</text>
          </svg>
          <div style='display:flex;gap:14px;color:#778198;font-size:12px'><span><b style='color:#6374DC'>●</b> 서아의 기록</span><span><b style='color:#F2A365'>●</b> 평균 알림 간격</span></div>
          <div style='background:#EEF1FF;color:#68758E;padding:12px;border-radius:9px;font-size:13px;margin-top:16px'>💡 수유 간격과 수면 기록은 더 많은 기록이 쌓이면 정확하게 요약됩니다.</div>
        </div>
        """,unsafe_allow_html=True); return
    if selected=="성장":
        st.markdown("""
        <div style='background:#fff;border:1px solid #E3E7F1;border-radius:15px;padding:16px'>
          <div style='display:flex;justify-content:space-between;align-items:center'><h3 style='margin:0'>몸무게 변화</h3><span style='color:#6374DC;background:#EEF1FF;border-radius:8px;padding:7px 10px;font-size:13px'>몸무게</span></div>
          <svg viewBox='0 0 620 270' role='img' aria-label='서아의 몸무게 성장 그래프' style='width:100%;height:auto;margin-top:12px'>
            <rect x='55' y='34' width='535' height='156' rx='8' fill='#FFFFFF'/>
            <path d='M55 54H590 M55 102H590 M55 150H590 M55 190H590' stroke='#E3E7F1' stroke-dasharray='4 4'/>
            <path d='M65 128 L195 106 L325 80 L455 55 L585 34 L585 68 L455 86 L325 111 L195 137 L65 158Z' fill='#DDE3FF' opacity='.9'/>
            <path d='M65 144 L195 122 L325 97 L455 72 L585 48' fill='none' stroke='#6374DC' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'/>
            <g fill='#6374DC'><circle cx='65' cy='144' r='5'/><circle cx='195' cy='122' r='5'/><circle cx='325' cy='97' r='5'/><circle cx='455' cy='72' r='5'/><circle cx='585' cy='48' r='5'/></g>
            <g fill='#778198' font-size='12'><text x='15' y='58'>5kg</text><text x='15' y='106'>4kg</text><text x='15' y='154'>3kg</text><text x='55' y='220'>출생</text><text x='171' y='220'>1주</text><text x='301' y='220'>2주</text><text x='431' y='220'>3주</text><text x='560' y='220'>현재</text></g>
            <text x='545' y='38' fill='#6374DC' font-size='12' font-weight='700'>4.2kg</text>
          </svg>
          <div style='display:flex;gap:14px;color:#778198;font-size:12px'><span><b style='color:#6374DC'>●</b> 서아</span><span><b style='color:#DDE3FF'>●</b> 같은 성별·월령 참고 범위</span></div>
          <h3 style='margin:22px 0 10px'>최근 측정 결과</h3>
          <div style='background:#EEF1FF;padding:12px;border-radius:9px'><b>현재 몸무게 4.2kg</b><br><span style='color:#68758E;font-size:13px'>성장 추세는 참고 정보이며 정상·비정상을 단정하지 않습니다.</span></div>
        </div>
        """,unsafe_allow_html=True); return
    if selected=="예방접종":
        v=api.get_vaccinations(st.session_state.baby_id)["data"]
        items=''.join(f"<p style='border-bottom:1px solid #E3E7F1;padding:10px'>✓　<b>{n}</b><span style='float:right;color:#20A26B'>{s}</span><br><small>　　{d}</small></p>" for n,d,s,_ in v['items'])
        st.markdown(f"<div style='background:#fff;border:1px solid #E3E7F1;border-radius:15px;padding:16px'><div style='background:#EEF1FF;padding:12px;border-radius:10px'><b>다음 예방접종 · {v['next']['name']}</b><span style='float:right;color:#6374DC'>{v['next']['date']}</span></div><h3>접종 내역 및 일정</h3>{items}</div>",unsafe_allow_html=True); return
    if st.session_state.editing_record_index is not None:
        index = st.session_state.editing_record_index
        record = records[index]
        with st.form("care_record_edit_form"):
            st.markdown("#### 육아 기록 수정")
            title = st.text_input("기록 제목", value=record["title"])
            detail = st.text_input("상세 내용", value=record["detail"])
            left, right = st.columns(2)
            if left.form_submit_button("저장하기", type="primary", use_container_width=True):
                st.session_state.care_record_overrides[index] = {"title": title, "detail": detail}
                st.session_state.editing_record_index = None
                st.query_params.clear()
                st.query_params.update({"demo": "1", "page": "육아 관리"})
                st.toast("육아 기록을 수정했습니다.")
                st.rerun()
            if right.form_submit_button("취소", use_container_width=True):
                st.session_state.editing_record_index = None
                st.query_params.clear()
                st.query_params.update({"demo": "1", "page": "육아 관리"})
                st.rerun()
        return
    pattern = api.get_care_pattern(st.session_state.baby_id)["data"]
    vaccination = api.get_vaccinations(st.session_state.baby_id)["data"]
    with st.expander("💩 기저귀 사진 분석", expanded=False):
        uploaded_image = st.file_uploader("기저귀 사진", type=["jpg", "jpeg", "png"], key="diaper_image")
        has_fever = st.checkbox("열이 있어요", key="diaper_fever")
        stool_count = st.number_input("최근 24시간 대변 횟수", min_value=0, max_value=30, value=0, key="diaper_count")
        if st.button("사진 분석하기", key="analyze_diaper", type="primary"):
            if uploaded_image is None:
                st.warning("분석할 사진을 선택해 주세요.")
            else:
                feeding = {"모유": "breast", "분유": "formula", "혼합": "mixed"}.get(baby["feeding_type"], "mixed")
                response = api.analyze_diaper_image(uploaded_image, st.session_state.baby_id, st.session_state.session_id, st.session_state.user_id, feeding, has_fever, int(stool_count))
                if response["success"]:
                    result = response["data"]
                    if not result["is_analyzable"]:
                        st.info("다시 촬영해 주세요: " + " ".join(result["quality_issues"]))
                    else:
                        risk = result["risk"] or {}
                        st.success("사진에서 보이는 특징을 정리했습니다.")
                        st.json({"observation": result["observation"], "risk": risk, "follow_up_questions": result["follow_up_questions"]})
                    st.caption(result["safety_notice"])
                else:
                    st.error(response["message"])
    st.markdown(
        f"""
        <style>
        .care-ai-analysis{{background:#EEF1FF;border:1px solid #C9D2FF;border-radius:15px;padding:16px;margin:16px 0}}.care-ai-analysis-title{{font-size:17px;font-weight:800;color:#202737}}.care-ai-analysis-sub{{font-size:13px;color:#68758E;margin:4px 0 12px}}.care-ai-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.care-ai-item{{background:#FFFFFF;border:1px solid #E3E7F1;border-radius:10px;padding:11px;font-size:13px;color:#68758E}}.care-ai-item b{{display:block;color:#202737;margin-bottom:4px}}@media(max-width:700px){{.care-ai-grid{{grid-template-columns:1fr}}}}
        </style>
        <div class="care-ai-analysis"><div class="care-ai-analysis-title">✨ AI 육아 분석 요약</div><div class="care-ai-analysis-sub">최근 육아 기록과 월령 정보를 함께 분석한 참고 안내예요.</div><div class="care-ai-grid"><div class="care-ai-item"><b>🍼 육아 기록</b>최근 7일 수유 47회로, 기록이 꾸준히 쌓이고 있어요.</div><div class="care-ai-item"><b>🌙 생활 패턴</b>평균 수유 간격은 {pattern['average_interval']}이며, 현재 알림 간격과 비슷해요.</div><div class="care-ai-item"><b>📈 성장</b>현재 몸무게 4.2kg으로 성장 추세를 계속 관찰해 주세요.</div><div class="care-ai-item"><b>💉 예방접종</b>다음 접종은 {vaccination['next']['name']}이며 {vaccination['next']['date']}에 예정되어 있어요.</div></div></div>
        """,
        unsafe_allow_html=True,
    )
    rows=''.join(f"<div class='r'><span>{x['time']}</span><b>{x['icon']}　{x['title']}</b><small>{x['detail']}</small><i><a class='edit-record' target='_self' href='?demo=1&amp;page=%EC%9C%A1%EC%95%84%20%EA%B4%80%EB%A6%AC&amp;edit_record={index}' aria-label='{x['title']} 수정'>✎</a></i></div>" for index, x in enumerate(records))
    st.markdown("<style>.filter{display:none!important}</style>", unsafe_allow_html=True)
    st.markdown("<style>.edit-record,.edit-record:link,.edit-record:visited{text-decoration:none!important;color:#778198;font-size:18px}.edit-record:hover{color:#6374DC}</style>", unsafe_allow_html=True)
    st.markdown("<style>@media(max-width:700px){.cardx .r{grid-template-columns:96px minmax(0,1fr) 32px!important;grid-template-rows:auto auto;column-gap:8px;row-gap:3px;padding:12px}.cardx .r>span{grid-column:1;grid-row:1 / 3;align-self:center;font-size:13px}.cardx .r>b{grid-column:2;grid-row:1;margin:0;font-size:15px;line-height:1.35}.cardx .r>small{grid-column:2;grid-row:2;margin:0;font-size:13px;line-height:1.4}.cardx .r>i{grid-column:3;grid-row:1 / 3;align-self:center;text-align:center}}</style>", unsafe_allow_html=True)
    st.markdown(f'''<style>.metrics{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}.m,.cardx{{background:#fff;border:1px solid #E3E7F1;border-radius:15px;padding:14px}}.m small,.r span,.r small{{color:#778198;font-size:13px}}.m b{{display:block;font-size:17px;margin-top:7px}}.cardx{{margin-top:16px}}.r{{display:grid;grid-template-columns:86px 1fr 2fr 65px;align-items:center;border:1px solid #E3E7F1;border-radius:12px;padding:11px;margin:8px 0;font-size:14px}}.r small{{display:block;margin-top:4px}}.r i{{color:#778198;font-style:normal;text-align:right}}.filter{{float:right;color:#6374DC;font-size:13px}}.note{{background:#EEF1FF;color:#68758E;border-radius:9px;padding:10px;font-size:13px;margin-top:10px}}</style><div class='metrics'><div class='m'><small>최근 7일 수유</small><b>47 <em>회</em></b></div><div class='m'><small>평균 수유량</small><b>96 <em>ml</em></b></div><div class='m'><small>하루 평균 수면</small><b>14.2 <em>시간</em></b></div><div class='m'><small>최근 7일 배변</small><b>19 <em>회</em></b></div></div><div class='cardx'><b>최근 기록</b><span class='filter'>전체　 수유　 수면　 배변　 성장</span>{rows}<div class='note'>수정·삭제는 보호자가 최종 확인한 뒤 반영됩니다.</div></div>''',unsafe_allow_html=True)
