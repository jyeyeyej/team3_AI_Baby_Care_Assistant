from __future__ import annotations
from datetime import date, datetime, time, timedelta
from html import escape
import math

import streamlit as st
import api
from common import render_page_header


def _display_care_records(result: dict) -> list[dict]:
    """Convert the saved Care API records into the compact recent-record cards."""
    data = result.get("data", [])
    raw_records = data.get("records", []) if isinstance(data, dict) else data
    if not isinstance(raw_records, list):
        return []

    labels = {
        "feeding": ("🍼", "수유"),
        "sleep": ("🌙", "수면"),
        "diaper": ("💩", "기저귀"),
        "growth": ("📏", "성장 측정"),
    }
    feeding_labels = {"formula": "분유", "breast": "모유", "mixed": "혼합 수유"}
    cards = []
    for record in raw_records:
        event_type = record.get("event_type", "")
        icon, title = labels.get(event_type, ("📝", "육아 기록"))
        details = record.get("details") or {}
        if event_type == "feeding":
            title = f"{feeding_labels.get(details.get('feeding_type'), '수유')} 수유"
            detail = f"{details.get('amount_ml', '확인 필요')}ml · 저장된 기록"
        elif event_type == "sleep":
            minutes = details.get("duration_minutes")
            detail = (
                f"{minutes // 60}시간" + (f" {minutes % 60}분" if minutes % 60 else "") + " 수면"
                if isinstance(minutes, int) else "저장된 수면 기록"
            )
        elif event_type == "growth":
            values = []
            if details.get("weight_kg") is not None:
                values.append(f"몸무게 {details['weight_kg']}kg")
            if details.get("height_cm") is not None:
                values.append(f"키 {details['height_cm']}cm")
            detail = " · ".join(values) or "저장된 성장 기록"
        else:
            kinds = "소변·대변" if details.get("urine") and details.get("stool") else "소변" if details.get("urine") else "대변"
            title = f"기저귀 · {kinds}"
            detail = " · ".join(
                part for part in (details.get("color"), details.get("consistency"), details.get("memo"), details.get("note")) if part
            ) or ("소변 기록 완료" if details.get("urine") and not details.get("stool") else "저장된 기록")

        recorded_at = str(record.get("recorded_at", ""))
        try:
            recorded_time = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
            time_label = f"오늘 {recorded_time.astimezone().strftime('%H:%M')}"
        except ValueError:
            time_label = "오늘"
        cards.append({
            "log_id": record.get("log_id") or record.get("id"),
            "time": time_label,
            "icon": icon,
            "title": title,
            "detail": detail,
            "event_type": event_type,
            "_recorded_at": recorded_at,
        })
    cards.sort(key=lambda card: card["_recorded_at"], reverse=True)
    return cards


def _validate_sleep_duration(start_time: time, end_time: time) -> tuple[int | None, str | None]:
    """Return a sleep duration, treating an earlier end time as the next day."""
    start_minutes = start_time.hour * 60 + start_time.minute
    end_minutes = end_time.hour * 60 + end_time.minute
    duration_minutes = end_minutes - start_minutes
    if duration_minutes <= 0:
        duration_minutes += 24 * 60
    if duration_minutes > 720:
        return None, "수면 시간은 최대 12시간까지 기록할 수 있어요."
    return duration_minutes, None

def render() -> None:
    baby=api.get_baby(st.session_state.baby_id, user_id=st.session_state.user_id, session_id=st.session_state.session_id)["data"]
    records_result = api.get_care_records(
        st.session_state.baby_id,
        user_id=st.session_state.user_id,
        session_id=st.session_state.session_id,
        days=3,
    )
    # Keep the recent-record card compact even when many logs have accumulated.
    records = _display_care_records(records_result)[:6]
    summary_result = api.get_care_summary(
        st.session_state.baby_id,
        user_id=st.session_state.user_id,
        session_id=st.session_state.session_id,
    )
    summary = summary_result.get("data", {}) if summary_result.get("success") else {}
    reminder_result = api.get_feeding_reminder(
        st.session_state.baby_id,
        user_id=st.session_state.user_id,
        session_id=st.session_state.session_id,
    )
    reminder_minutes = (reminder_result.get("data") or {}).get("feeding_interval_minutes", 180)
    reminder_hours, reminder_remaining_minutes = divmod(int(reminder_minutes), 60)
    reminder_interval_label = f"{reminder_hours}시간" + (f" {reminder_remaining_minutes}분" if reminder_remaining_minutes else "")
    feeding_summary = summary.get("feeding", {})
    sleep_summary = summary.get("sleep", {})
    diaper_summary = summary.get("diaper", {})
    feeding_count = feeding_summary.get("count", 0)
    average_amount = feeding_summary.get("average_amount_ml")
    average_amount_label = f"{average_amount:g}" if isinstance(average_amount, (int, float)) else "-"
    daily_sleep_minutes = sleep_summary.get("daily_average_minutes", 0)
    sleep_hours, sleep_minutes = divmod(round(daily_sleep_minutes), 60) if isinstance(daily_sleep_minutes, (int, float)) else (0, 0)
    daily_sleep_label = f"{sleep_hours}.{round(sleep_minutes / 6)}" if sleep_minutes else str(sleep_hours)
    average_interval = feeding_summary.get("average_interval_minutes")
    if isinstance(average_interval, (int, float)):
        interval_hours, interval_minutes = divmod(round(average_interval), 60)
        average_interval_label = f"{interval_hours}시간" + (f" {interval_minutes}분" if interval_minutes else "")
    else:
        average_interval_label = "기록이 더 필요해요"
    stool_count = diaper_summary.get("stool_count", 0)
    daily_feeding_label = f"{feeding_summary.get('daily_average_count', 0):.1f}회"
    daily_diaper_label = f"{diaper_summary.get('daily_average_stool_count', 0):.1f}회"
    interval_days = feeding_summary.get("daily_intervals", [])
    st.session_state.setdefault("care_record_overrides", {})
    for index, override in st.session_state.care_record_overrides.items():
        if index < len(records):
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
    current_weight = float(baby["current_weight_kg"])
    growth_y = max(24, min(165, 132 - (20 * current_weight)))
    growth_label_y = max(20, growth_y - 10)
    st.markdown("<style>h3{font-size:18px!important}</style>", unsafe_allow_html=True)
    query_edit = st.query_params.get("edit_record")
    if query_edit is not None and query_edit.isdigit() and int(query_edit) in {0, 1, 2}:
        st.session_state.editing_record_index = int(query_edit)
    if selected=="생활 패턴":
        interval_values = [
            point.get("average_interval_minutes") / 60
            for point in interval_days
            if isinstance(point.get("average_interval_minutes"), (int, float))
        ]
        average_interval_hours = average_interval / 60 if isinstance(average_interval, (int, float)) else None
        chart_max = 5
        chart_min = 2
        chart_range = 3
        chart_x = [65 + 85 * index for index in range(7)]
        chart_points = []
        for index, point in enumerate(interval_days[:7]):
            value = point.get("average_interval_minutes")
            hours = value / 60 if isinstance(value, (int, float)) else None
            y = 173 - ((hours - chart_min) / chart_range * 135) if hours is not None else None
            chart_points.append((chart_x[index], y, point.get("weekday", "")))
        while len(chart_points) < 7:
            chart_points.append((chart_x[len(chart_points)], None, ""))
        chart_path_parts = []
        previous_point_missing = True
        for x, y, _ in chart_points:
            if y is None:
                previous_point_missing = True
                continue
            chart_path_parts.append(("M" if previous_point_missing else "L") + f"{x:.0f} {y:.1f}")
            previous_point_missing = False
        chart_path = " ".join(chart_path_parts)
        chart_circles = "".join(f"<circle cx='{x:.0f}' cy='{y:.1f}' r='4'/>" for x, y, _ in chart_points if y is not None)
        weekday_labels = "".join(f"<text x='{x - 10:.0f}' y='211'>{escape(label)}</text>" for x, _, label in chart_points)
        grid_labels = "".join(
            f"<text x='12' y='{42 + index * 45}'>{hours}시간</text>"
            for index, hours in enumerate([5, 4, 3, 2])
        )
        average_y = 173 - ((average_interval_hours - chart_min) / chart_range * 135) if average_interval_hours is not None else None
        average_line = f"<path d='M55 {average_y:.1f}H590' stroke='#F2A365' stroke-width='2' stroke-dasharray='6 5'/><text x='435' y='{average_y - 7:.1f}' fill='#E58B42' font-size='12'>평균 수유 간격 {escape(average_interval_label)}</text>" if average_y is not None else ""
        st.markdown(f"""
        <div style='background:#fff;border:1px solid #E3E7F1;border-radius:15px;padding:16px'>
          <h3>생활 패턴</h3>
          <div style='display:grid;grid-template-columns:1fr 1fr;gap:10px'>
            <div style='background:#F4F6FB;padding:12px;border-radius:10px;color:#778198;font-size:13px'>평균 수유 간격<br><b style='color:#202737;font-size:17px'>{average_interval_label}</b></div>
            <div style='background:#F4F6FB;padding:12px;border-radius:10px;color:#778198;font-size:13px'>1일 평균 수유<br><b style='color:#202737;font-size:17px'>{daily_feeding_label}</b></div>
            <div style='background:#F4F6FB;padding:12px;border-radius:10px;color:#778198;font-size:13px'>평균 수면<br><b style='color:#202737;font-size:17px'>{daily_sleep_label}시간</b></div>
            <div style='background:#F4F6FB;padding:12px;border-radius:10px;color:#778198;font-size:13px'>1일 평균 배변<br><b style='color:#202737;font-size:17px'>{daily_diaper_label}</b></div>
          </div>
          <h4 style='margin:20px 0 2px'>최근 7일 수유 간격</h4>
          <div style='color:#778198;font-size:13px;margin-bottom:6px'>알림 간격 {reminder_interval_label} 기준</div>
          <svg viewBox='0 0 620 245' role='img' aria-label='최근 7일 수유 간격 그래프' style='width:100%;height:auto'>
            <path d='M55 38H590 M55 83H590 M55 128H590 M55 173H590' stroke='#E3E7F1' stroke-dasharray='4 4'/>
            {average_line}
            <path d='{chart_path}' fill='none' stroke='#6374DC' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'/>
            <g fill='#6374DC'>{chart_circles}</g>
            <g fill='#778198' font-size='12'>{grid_labels}{weekday_labels}</g>
          </svg>
          <div style='display:flex;gap:14px;color:#778198;font-size:12px'><span><b style='color:#6374DC'>●</b> {escape(baby['baby_name'])}의 기록</span><span><b style='color:#F2A365'>●</b> 평균 수유 간격 ({average_interval_label})</span></div>
          <div style='background:#EEF1FF;color:#68758E;padding:12px;border-radius:9px;font-size:13px;margin-top:16px'>💡 수유 간격과 수면 기록은 더 많은 기록이 쌓이면 정확하게 요약됩니다.</div>
        </div>
        """,unsafe_allow_html=True); return
    if selected=="성장":
        st.markdown(f"""
        <div style='background:#fff;border:1px solid #E3E7F1;border-radius:15px;padding:16px'>
          <div style='display:flex;justify-content:space-between;align-items:center'><h3 style='margin:0'>몸무게 변화</h3><span style='color:#6374DC;background:#EEF1FF;border-radius:8px;padding:7px 10px;font-size:13px'>몸무게</span></div>
          <svg viewBox='0 0 620 270' role='img' aria-label='{escape(baby['baby_name'])}의 몸무게 성장 그래프' style='width:100%;height:auto;margin-top:12px'>
            <rect x='55' y='34' width='535' height='156' rx='8' fill='#FFFFFF'/>
            <path d='M55 54H590 M55 102H590 M55 150H590 M55 190H590' stroke='#E3E7F1' stroke-dasharray='4 4'/>
            <path d='M65 128 L195 106 L325 80 L455 55 L585 34 L585 68 L455 86 L325 111 L195 137 L65 158Z' fill='#DDE3FF' opacity='.9'/>
            <path d='M65 144 L195 122 L325 97 L455 72 L585 {growth_y}' fill='none' stroke='#6374DC' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'/>
            <g fill='#6374DC'><circle cx='65' cy='144' r='5'/><circle cx='195' cy='122' r='5'/><circle cx='325' cy='97' r='5'/><circle cx='455' cy='72' r='5'/><circle cx='585' cy='{growth_y}' r='5'/></g>
            <g fill='#778198' font-size='12'><text x='15' y='58'>5kg</text><text x='15' y='106'>4kg</text><text x='15' y='154'>3kg</text><text x='55' y='220'>출생</text><text x='171' y='220'>1주</text><text x='301' y='220'>2주</text><text x='431' y='220'>3주</text><text x='560' y='220'>현재</text></g>
            <text x='545' y='{growth_label_y}' fill='#6374DC' font-size='12' font-weight='700'>{current_weight:.1f}kg</text>
          </svg>
          <div style='display:flex;gap:14px;color:#778198;font-size:12px'><span><b style='color:#6374DC'>●</b> {escape(baby['baby_name'])}</span><span><b style='color:#DDE3FF'>●</b> 같은 성별·월령 참고 범위</span></div>
          <h3 style='margin:22px 0 10px'>최근 측정 결과</h3>
          <div style='background:#EEF1FF;padding:12px;border-radius:9px'><b>현재 몸무게 {current_weight:.1f}kg</b><br><span style='color:#68758E;font-size:13px'>{escape(baby['baby_name'])}가 건강하게 성장하고 있어요. 지금처럼 꾸준히 성장 기록을 확인해 주세요.</span></div>
        </div>
        """,unsafe_allow_html=True); return
    if selected=="예방접종":
        v=api.get_vaccinations(st.session_state.baby_id)["data"]
        items=''.join(f"<p style='border-bottom:1px solid #E3E7F1;padding:10px'>✓　<b>{n}</b><span style='float:right;color:#20A26B'>{s}</span><br><small>　　{d}</small></p>" for n,d,s,_ in v['items'])
        st.markdown(f"<style>@media(max-width:700px){{.next-vaccination-date{{display:block;float:none!important;margin-top:6px;text-align:right}}}}</style><div style='background:#fff;border:1px solid #E3E7F1;border-radius:15px;padding:16px'><div style='background:#EEF1FF;padding:12px;border-radius:10px'><b>다음 예방접종 · {v['next']['name']}</b><span class='next-vaccination-date' style='float:right;color:#6374DC'>{v['next']['date']}</span></div><h3>접종 내역 및 일정</h3>{items}</div>",unsafe_allow_html=True); return
    if st.session_state.editing_record_index is not None:
        index = st.session_state.editing_record_index
        # Quick-record links preserve the original three dedicated edit screens
        # even when today's live list does not yet contain that record type.
        fallback_records = {
            0: {"title": "분유 수유", "detail": "100ml · 알림 확인으로 기록"},
            1: {"title": "낮잠 종료", "detail": "10:20–12:05 · 1시간 45분"},
            2: {"title": "기저귀 · 대변", "detail": "노란색, 묽은 형태 · 사진 분석 메모 있음"},
        }
        # URL navigation is normalized elsewhere, so keep this mode in the
        # Streamlit session instead of relying only on a query parameter.
        is_quick_edit = st.session_state.quick_edit_mode
        record = fallback_records.get(index) if is_quick_edit else (
            records[index] if index < len(records) else fallback_records.get(index)
        )
        if record is None:
            st.session_state.editing_record_index = None
            st.query_params.clear()
            st.query_params.update({"page": "육아 관리"})
            st.rerun()
        event_type = (
            {0: "feeding", 1: "sleep", 2: "diaper"}.get(index, "feeding")
            if is_quick_edit else st.session_state.editing_record_type or record.get("event_type", "feeding")
        )
        if event_type == "sleep":
            st.markdown("#### 수면 기록")
            start_column, end_column = st.columns(2)
            start_time = start_column.time_input("시작 시간", value=time(10, 20), key="sleep_start_time")
            end_time = end_column.time_input("종료 시간", value=time(11, 50), key="sleep_end_time")
            duration_minutes, sleep_error = _validate_sleep_duration(start_time, end_time)
            if sleep_error:
                st.caption(sleep_error)
            else:
                hours, minutes = divmod(duration_minutes, 60)
                duration_label = f"{hours}시간" + (f" {minutes}분" if minutes else "")
                st.caption(f"총 수면 시간: {duration_label}")
            save_column, cancel_column = st.columns(2)
            if save_column.button("저장하기", type="primary", use_container_width=True, key="save_sleep_record"):
                if sleep_error:
                    st.error(sleep_error)
                    return
                if is_quick_edit:
                    result = api.create_quick_care_log(
                        st.session_state.baby_id,
                        event_type="sleep",
                        duration_minutes=duration_minutes,
                        recorded_at=datetime.now().astimezone().isoformat(),
                        session_id=st.session_state.session_id,
                        user_id=st.session_state.user_id,
                    )
                    if not result.get("success"):
                        st.error(result.get("message", "수면 기록을 저장하지 못했습니다."))
                        return
                else:
                    st.session_state.care_record_overrides[index] = {
                        "title": "낮잠",
                        "detail": f"{start_time.strftime('%H:%M')}–{end_time.strftime('%H:%M')} · {duration_label}",
                    }
                st.session_state.editing_record_index = None
                st.session_state.editing_record_type = None
                st.session_state.quick_edit_mode = False
                st.query_params.clear()
                st.query_params.update({"demo": "1", "page": "육아 관리"})
                st.toast("수면 기록을 저장했습니다.")
                st.rerun()
            if cancel_column.button("취소", use_container_width=True, key="cancel_sleep_record"):
                st.session_state.editing_record_index = None
                st.session_state.editing_record_type = None
                st.session_state.quick_edit_mode = False
                st.query_params.clear()
                st.query_params.update({"demo": "1", "page": "육아 관리"})
                st.rerun()
            return
        with st.form("care_record_edit_form"):
            if event_type == "feeding":
                st.markdown("#### 수유 기록")
                feeding_type = st.selectbox("수유 방식", ["분유", "모유", "혼합"])
                amount_ml = st.selectbox("수유량", [80, 100, 120, 140, 160], index=1, format_func=lambda value: f"{value}ml")
                title, detail = f"{feeding_type} 수유", f"{amount_ml}ml"
                quick_payload = {"event_type": "feeding", "feeding_type": {"분유": "formula", "모유": "breast", "혼합": "mixed"}[feeding_type], "amount_ml": amount_ml}
            elif event_type == "sleep":
                st.markdown("#### 수면 기록")
                start_column, end_column = st.columns(2)
                start_time = start_column.time_input("시작 시간", value=time(10, 20))
                end_time = end_column.time_input("종료 시간", value=time(11, 50))
                duration_minutes, sleep_error = _validate_sleep_duration(start_time, end_time)
                title = "낮잠"
                if sleep_error:
                    duration_label = ""
                    detail = "수면 시간을 확인해 주세요"
                    st.caption(sleep_error)
                else:
                    hours, minutes = divmod(duration_minutes, 60)
                    duration_label = f"{hours}시간" + (f" {minutes}분" if minutes else "")
                    detail = f"{start_time.strftime('%H:%M')}–{end_time.strftime('%H:%M')} · {duration_label}"
                    st.caption(f"총 수면 시간: {duration_label}")
                quick_payload = {
                    "event_type": "sleep",
                    "duration_minutes": duration_minutes,
                    "recorded_at": started_at.isoformat(),
                }
            else:
                st.markdown("#### 기저귀 기록")
                urine = st.checkbox("소변", value=False)
                stool = st.checkbox("대변", value=True)
                color = None
                consistency = None
                if stool:
                    color_choice = st.selectbox(
                        "대변 색상",
                        ["노란색", "황록색", "초록색", "갈색", "검은색", "흰색/회백색", "붉은색", "직접 입력"],
                    )
                    color = (
                        st.text_input("대변 색상 직접 입력", placeholder="색상을 입력해 주세요")
                        if color_choice == "직접 입력" else color_choice
                    )
                    consistency_choice = st.selectbox(
                        "대변 질감",
                        ["묽은 편", "보통", "되직한 편", "물설사처럼 매우 묽음", "덩어리짐", "점액이 섞임", "직접 입력"],
                    )
                    consistency = (
                        st.text_input("대변 질감 직접 입력", placeholder="질감을 입력해 주세요")
                        if consistency_choice == "직접 입력" else consistency_choice
                    )
                else:
                    st.text_input("대변 상태", value="없음", disabled=True)
                note = st.text_input("메모 (선택)", placeholder="추가로 남길 내용을 입력해 주세요")
                title = "기저귀 · " + ("소변·대변" if urine and stool else "소변" if urine else "대변")
                detail = " · ".join(part for part in (color, consistency, note) if part) or "저장된 기저귀 기록"
                quick_payload = {
                    "event_type": "diaper",
                    "urine": urine,
                    "stool": stool,
                    "color": color or None,
                    "consistency": consistency or None,
                    "note": note or None,
                }

            left, right = st.columns(2)
            if left.form_submit_button("저장하기", type="primary", use_container_width=True):
                if event_type == "sleep" and sleep_error:
                    st.error(sleep_error)
                    return
                if event_type == "diaper" and not urine and not stool:
                    st.error("소변 또는 대변을 하나 이상 선택해 주세요.")
                    return
                if is_quick_edit:
                    result = api.create_quick_care_log(
                        st.session_state.baby_id,
                        session_id=st.session_state.session_id,
                        user_id=st.session_state.user_id,
                        **quick_payload,
                    )
                    if not result.get("success"):
                        st.error(result.get("message", "육아 기록을 저장하지 못했습니다."))
                        return
                else:
                    st.session_state.care_record_overrides[index] = {"title": title, "detail": detail}
                st.session_state.editing_record_index = None
                st.session_state.editing_record_type = None
                st.session_state.quick_edit_mode = False
                st.query_params.clear()
                st.query_params.update({"demo": "1", "page": "육아 관리"})
                st.toast("육아 기록을 저장했습니다." if is_quick_edit else "육아 기록을 수정했습니다.")
                st.rerun()
            if right.form_submit_button("취소", use_container_width=True):
                st.session_state.editing_record_index = None
                st.session_state.editing_record_type = None
                st.session_state.quick_edit_mode = False
                st.query_params.clear()
                st.query_params.update({"demo": "1", "page": "육아 관리"})
                st.rerun()
        return
    vaccination = api.get_vaccinations(st.session_state.baby_id)["data"]
    st.markdown(
        f"""
        <style>
        .care-ai-analysis{{background:#EEF1FF;border:1px solid #C9D2FF;border-radius:15px;padding:16px;margin:16px 0 0}}.care-ai-analysis-title{{font-size:17px;font-weight:800;color:#202737}}.care-ai-analysis-sub{{font-size:13px;color:#68758E;margin:4px 0 12px}}.care-ai-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.care-ai-item{{background:#FFFFFF;border:1px solid #E3E7F1;border-radius:10px;padding:11px;font-size:13px;color:#68758E}}.care-ai-item b{{display:block;color:#202737;margin-bottom:4px}}@media(max-width:700px){{.care-ai-grid{{grid-template-columns:1fr}}}}
        </style>
        <div class="care-ai-analysis"><div class="care-ai-analysis-title">✨ AI 육아 분석 요약</div><div class="care-ai-analysis-sub">최근 육아 기록과 월령 정보를 함께 분석한 참고 안내예요.</div><div class="care-ai-grid"><div class="care-ai-item"><b>🍼 육아 기록</b>최근 7일 수유 {feeding_count}회가 저장되어 있어요.</div><div class="care-ai-item"><b>🌙 생활 패턴</b>평균 수유 간격은 {average_interval_label}이에요.</div><div class="care-ai-item"><b>📈 성장</b>현재 몸무게 {current_weight:.1f}kg으로 성장 추세를 계속 관찰해 주세요.</div><div class="care-ai-item"><b>💉 예방접종</b>다음 접종은 {vaccination['next']['name']}이며 {vaccination['next']['date']}에 예정되어 있어요.</div></div></div>
        """,
        unsafe_allow_html=True,
    )
    rows=''.join(f"<div class='r'><span>{x['time']}</span><b>{x['icon']}　{x['title']}</b><small>{x['detail']}</small><i><a class='edit-record' target='_self' href='?demo=1&amp;page=%EC%9C%A1%EC%95%84%20%EA%B4%80%EB%A6%AC&amp;edit_record={index}' aria-label='{x['title']} 수정'>✎</a></i></div>" for index, x in enumerate(records))
    st.markdown("<style>.filter{display:none!important}</style>", unsafe_allow_html=True)
    st.markdown("<style>.edit-record,.cardx{display:none!important}</style>", unsafe_allow_html=True)
    metrics_placeholder = st.empty()
    st.markdown("<style>.st-key-recent_records_controls{gap:10px!important}.st-key-recent_records_controls [data-testid='stVerticalBlock']{gap:0!important}.st-key-recent_records_controls [data-testid='stHorizontalBlock']{border:1px solid #E3E7F1;border-radius:12px;padding:8px 12px;margin:0!important;align-items:center}.st-key-recent_records_controls [data-testid='stHorizontalBlock'] button{min-height:36px;padding:0 .55rem}.recent-record-title{display:inline-block;width:13rem;font-size:.9rem}.recent-record-detail{color:#778198;font-size:.82rem;margin-left:0}@media(max-width:700px){.st-key-recent_records_controls{gap:10px!important}.st-key-recent_records_controls [data-testid='stVerticalBlock']{gap:0!important}.st-key-recent_records_controls [data-testid='stHorizontalBlock']{flex-wrap:nowrap!important;gap:.35rem!important;padding:10px!important}.st-key-recent_records_controls [data-testid='stHorizontalBlock']>[data-testid='stColumn']{min-width:0!important}.st-key-recent_records_controls [data-testid='stHorizontalBlock']>[data-testid='stColumn']:first-child{flex:0 0 94px!important;width:94px!important}.st-key-recent_records_controls [data-testid='stHorizontalBlock']>[data-testid='stColumn']:nth-child(2){flex:1 1 auto!important;width:auto!important}.st-key-recent_records_controls [data-testid='stHorizontalBlock']>[data-testid='stColumn']:nth-child(3),.st-key-recent_records_controls [data-testid='stHorizontalBlock']>[data-testid='stColumn']:nth-child(4){flex:0 0 38px!important;width:38px!important}.st-key-recent_records_controls [data-testid='stHorizontalBlock'] button{min-height:32px!important;min-width:32px!important;padding:0!important}.recent-record-title{display:block;width:auto}.recent-record-detail{display:block;margin:.2rem 0 0!important}}</style>", unsafe_allow_html=True)
    st.session_state.setdefault("delete_care_record_id", None)
    with st.container(key="recent_records_controls", border=True):
        st.markdown("<div class='section-title'>최근 기록</div>", unsafe_allow_html=True)
        for index, record in enumerate(records):
            time_column, content_column, edit_column, delete_column = st.columns([1.05, 4.2, 0.35, 0.35])
            time_column.caption(record["time"])
            content_column.markdown(
                f"<b class='recent-record-title'>{escape(record['icon'])}　{escape(record['title'])}</b><span class='recent-record-detail'>{escape(record['detail'])}</span>",
                unsafe_allow_html=True,
            )
            if edit_column.button("✎", key=f"edit_saved_record_{index}", help=f"{record['title']} 수정"):
                st.session_state.editing_record_index = index
                st.session_state.editing_record_type = record.get("event_type")
                st.session_state.quick_edit_mode = False
                st.rerun()
            log_id = record.get("log_id")
            if log_id and st.session_state.delete_care_record_id == log_id:
                if delete_column.button("삭제 확인", key=f"confirm_delete_record_{index}", type="primary"):
                    result = api.delete_care_log(
                        log_id,
                        user_id=st.session_state.user_id,
                        session_id=st.session_state.session_id,
                    )
                    if result.get("success"):
                        st.session_state.delete_care_record_id = None
                        st.toast("육아 기록을 삭제했습니다.")
                        st.rerun()
                    st.error(result.get("message", "육아 기록을 삭제하지 못했습니다."))
                if delete_column.button("취소", key=f"cancel_delete_record_{index}"):
                    st.session_state.delete_care_record_id = None
                    st.rerun()
            elif delete_column.button("🗑", key=f"delete_record_{index}", help=f"{record['title']} 삭제", disabled=not bool(log_id)):
                st.session_state.delete_care_record_id = log_id
                st.rerun()
        st.caption("수정·삭제는 보호자가 최종 확인한 뒤 반영됩니다.")
    st.markdown("<style>@media(max-width:700px){.cardx .r{grid-template-columns:96px minmax(0,1fr) 32px!important;grid-template-rows:auto auto;column-gap:8px;row-gap:3px;padding:12px}.cardx .r>span{grid-column:1;grid-row:1 / 3;align-self:center;font-size:13px}.cardx .r>b{grid-column:2;grid-row:1;margin:0;font-size:15px;line-height:1.35}.cardx .r>small{grid-column:2;grid-row:2;margin:0;font-size:13px;line-height:1.4}.cardx .r>i{grid-column:3;grid-row:1 / 3;align-self:center;text-align:center}}</style>", unsafe_allow_html=True)
    metrics_placeholder.markdown(f'''<style>.metrics{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}.m,.cardx{{background:#fff;border:1px solid #E3E7F1;border-radius:15px;padding:14px}}.m small,.r span,.r small{{color:#778198;font-size:13px}}.m b{{display:block;font-size:17px;margin-top:7px;color:#6374DC}}.cardx{{margin-top:16px}}.r{{display:grid;grid-template-columns:86px 1fr 2fr 65px;align-items:center;border:1px solid #E3E7F1;border-radius:12px;padding:11px;margin:8px 0;font-size:14px}}.r small{{display:block;margin-top:4px}}.r i{{color:#778198;font-style:normal;text-align:right}}.filter{{float:right;color:#6374DC;font-size:13px}}.note{{background:#EEF1FF;color:#68758E;border-radius:9px;padding:10px;font-size:13px;margin-top:10px}}</style><div class='metrics'><div class='m'><small>최근 7일 수유</small><b>{feeding_count} <em>회</em></b></div><div class='m'><small>평균 수유량</small><b>{average_amount_label} <em>ml</em></b></div><div class='m'><small>하루 평균 수면</small><b>{daily_sleep_label} <em>시간</em></b></div><div class='m'><small>최근 7일 배변</small><b>{stool_count} <em>회</em></b></div></div><div class='cardx'><b>최근 기록</b><span class='filter'>전체　 수유　 수면　 배변　 성장</span>{rows}<div class='note'>수정·삭제는 보호자가 최종 확인한 뒤 반영됩니다.</div></div>''',unsafe_allow_html=True)
