"""考试选择页面 — 两种入口：基于简历 / 直接输入"""

import json
import time
import streamlit as st

from db.database import (
    init_db, get_all_candidates, insert_candidate_manual,
    create_exam_session, get_exam_sessions,
)
from services.exam_engine import (
    TRACK_LABELS, TRACK_DESCRIPTIONS, load_track_questions, load_shared_questions,
    load_psychology_questions, select_exam_questions,
)

from services.auth import is_authenticated, get_current_role

init_db()

st.set_page_config(page_title="考试选择", page_icon="📝", layout="wide")

if not is_authenticated():
    st.warning("请先登录或使用邀请链接 / Please login or use an invite link")
    st.stop()

st.title("📝 考试选择 Exam Selection")
_role = get_current_role()

# ─── Helper: start exam and navigate ───

def start_exam(candidate_id, track_key, time_limit, num_questions):
    """Create exam session, store in session state, navigate to exam page."""
    questions = select_exam_questions(
        track=track_key,
        num_track=num_questions,
        num_iq=10,
        num_math=5,
    )
    if not questions:
        st.error("题库为空，请先添加题目")
        return

    session_id = create_exam_session(
        candidate_id=candidate_id,
        track=track_key,
        time_limit_minutes=time_limit,
    )

    st.session_state["exam_session_id"] = session_id
    st.session_state["exam_questions"] = questions
    st.session_state["exam_track"] = track_key
    st.session_state["exam_current_q"] = 0
    st.session_state["exam_answers"] = {}
    st.session_state["exam_time_limit"] = time_limit * 60
    st.session_state["exam_candidate_id"] = candidate_id
    st.session_state["exam_start_time"] = time.time()

    st.success(f"考试已创建！共 {len(questions)} 道题，限时 {time_limit} 分钟")
    st.switch_page("pages/3_⏱_Exam_Interface.py")


# ═══════════════════════════════════════════
# Two entry modes
# ═══════════════════════════════════════════

tab_resume, tab_manual = st.tabs(["📋 基于简历 (From Resume)", "✏️ 直接输入 (Quick Entry)"])

# ─── Tab 1: From Resume ───
with tab_resume:
    candidates = get_all_candidates()

    if not candidates:
        st.info("暂无候选人，请先在「简历筛选」页面上传简历，或使用「直接输入」模式")
    else:
        candidate_options = {}
        for c in candidates:
            parsed = json.loads(c.get("parsed_data", "{}")) if isinstance(c.get("parsed_data"), str) else c.get("parsed_data", {})
            label = f"{parsed.get('name', c.get('name', 'N/A'))} ({c.get('resume_filename', '')})"
            candidate_options[c["id"]] = label

        selected_candidate_id = st.selectbox(
            "选择候选人",
            list(candidate_options.keys()),
            format_func=lambda x: candidate_options[x],
            key="resume_candidate",
        )

        # Show candidate info
        if selected_candidate_id:
            cand = next((c for c in candidates if c["id"] == selected_candidate_id), None)
            if cand:
                parsed = json.loads(cand.get("parsed_data", "{}")) if isinstance(cand.get("parsed_data"), str) else cand.get("parsed_data", {})
                info_cols = st.columns(4)
                info_cols[0].markdown(f"**姓名**: {parsed.get('name', 'N/A')}")
                edu = parsed.get("education", [])
                if edu:
                    info_cols[1].markdown(f"**学校**: {edu[0].get('school', 'N/A')}")
                    info_cols[2].markdown(f"**学位**: {edu[0].get('degree', 'N/A')}")
                exp = parsed.get("experience", [])
                total_years = sum(e.get("years", 0) for e in exp)
                info_cols[3].markdown(f"**工作年限**: {total_years:.1f} 年")

                if exp:
                    exp_strs = ["{} ({})".format(e.get("company", ""), e.get("title", "")) for e in exp[:3]]
                    st.markdown("**经历**: " + ", ".join(exp_strs))

            # Show existing sessions
            existing = get_exam_sessions(selected_candidate_id)
            if existing:
                st.markdown("**已有考试记录:**")
                for s in existing:
                    status_icon = "✅" if s["status"] == "completed" else "⏳"
                    score_str = f" — {s.get('total_score', 0):.1f}/{s.get('max_score', 0):.0f}" if s["status"] == "completed" else ""
                    st.markdown(f"- {status_icon} {TRACK_LABELS.get(s['track'], s['track'])}{score_str}")

        st.session_state["_entry_mode"] = "resume"
        st.session_state["_resume_candidate_id"] = selected_candidate_id if candidates else None

# ─── Tab 2: Quick Entry ───
with tab_manual:
    st.markdown("直接输入候选人信息，无需上传简历即可开始考试。")

    col1, col2 = st.columns(2)
    with col1:
        manual_name = st.text_input("姓名 *", placeholder="张三", key="manual_name")
        manual_school = st.text_input("学校", placeholder="清华大学", key="manual_school")
    with col2:
        manual_track = st.selectbox(
            "考核方向 *",
            list(TRACK_LABELS.keys()),
            format_func=lambda x: TRACK_LABELS[x],
            key="manual_track",
        )
        manual_domain = st.selectbox(
            "领域",
            ["Cross-Sectional (截面)", "Time-Series (时序)", "High-Frequency (高频)", "Alternative Data (另类数据)"],
            key="manual_domain",
        )

    st.session_state["_entry_mode"] = "manual"

# ═══════════════════════════════════════════
# Track Selection Cards (shared by both tabs)
# ═══════════════════════════════════════════

st.markdown("---")
st.subheader("选择考核方向并开始考试")

cols = st.columns(2)

for i, (track_key, track_label) in enumerate(TRACK_LABELS.items()):
    with cols[i % 2]:
        with st.container(border=True):
            st.markdown(f"### {track_label}")
            st.markdown(TRACK_DESCRIPTIONS.get(track_key, ""))

            track_qs = load_track_questions(track_key)
            shared_qs = load_shared_questions()
            psych_qs = load_psychology_questions()
            psych_count = len([q for q in psych_qs if "PSY" in q.get("id", "")])
            char_count = len([q for q in psych_qs if "CHR" in q.get("id", "")])

            st.markdown("📚 题库: **{}** 专业 | **{}** IQ/数学 | **{}** 心理素质 | **{}** 职业素养".format(
                len(track_qs), len(shared_qs), psych_count, char_count))

            st.caption("每次考试: 30 专业 + 3 IQ/数学 + 20 综合素质 = **53 道选择题**")

            time_limit = st.number_input(
                "考试时长（分钟）", min_value=30, max_value=300, value=90,
                key="time_{}".format(track_key),
            )

            if st.button("🚀 开始 {} 考试".format(track_label), key="start_{}".format(track_key), type="primary"):
                entry_mode = st.session_state.get("_entry_mode", "manual")

                if entry_mode == "resume":
                    cid = st.session_state.get("_resume_candidate_id")
                    if not cid:
                        st.error("请先选择候选人")
                    else:
                        start_exam(cid, track_key, time_limit, 30)

                else:  # manual
                    name = st.session_state.get("manual_name", "").strip()
                    if not name:
                        st.error("请输入候选人姓名")
                    else:
                        school = st.session_state.get("manual_school", "")
                        cid = insert_candidate_manual(name, school, track_key)
                        start_exam(cid, track_key, time_limit, 30)
