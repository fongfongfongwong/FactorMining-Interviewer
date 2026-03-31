"""考试选择页面 — 管理员生成考试链接 / 候选人自选方向开始考试"""

import json
import time
import streamlit as st

from db.database import (
    init_db, get_all_candidates, insert_candidate_manual,
    create_exam_session, get_exam_sessions, create_invite_link,
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
        num_iq_math=3,
        num_psych=10,
        num_character=10,
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

    st.success("考试已创建！共 {} 道题，限时 {} 分钟".format(len(questions), time_limit))
    st.switch_page("pages/3_⏱_Exam_Interface.py")


# ═══════════════════════════════════════════
# ADMIN / OPERATOR VIEW: Generate exam links + manage
# ═══════════════════════════════════════════

if _role in ("admin", "operator"):

    tab_links, tab_resume, tab_manual = st.tabs([
        "🔗 生成考试链接 (Generate Exam Link)",
        "📋 基于简历 (From Resume)",
        "✏️ 直接输入 (Quick Entry)",
    ])

    # ─── Tab 1: Generate Exam Links ───
    with tab_links:
        st.markdown("### 生成考试邀请链接")
        st.markdown("创建链接发送给候选人，候选人打开链接 → 输入个人信息 → 选择方向 → 开始考试。")

        with st.form("gen_link_form"):
            col1, col2 = st.columns(2)
            with col1:
                link_name = st.text_input("候选人姓名（可选，候选人可自行填写）")
                link_email = st.text_input("候选人邮箱（可选）")
            with col2:
                link_track = st.selectbox(
                    "预分配考核方向",
                    [None] + list(TRACK_LABELS.keys()),
                    format_func=lambda x: "候选人自选" if x is None else TRACK_LABELS[x],
                )
                link_hours = st.number_input("链接有效期（小时）", min_value=1, max_value=720, value=72)

            submitted = st.form_submit_button("🔗 生成邀请链接", type="primary")

            if submitted:
                user_id = st.session_state.get("user_id")
                token = create_invite_link(
                    candidate_name=link_name,
                    candidate_email=link_email,
                    track=link_track,
                    created_by=user_id,
                    expires_hours=link_hours,
                )
                base_url = "http://localhost:8502"  # TODO: auto-detect or configure
                invite_url = "{}/?invite={}".format(base_url, token)
                st.success("✅ 邀请链接已生成！")
                st.code(invite_url, language=None)
                st.info("将此链接发送给候选人。候选人打开后填写信息即可开始考试。有效期 {} 小时。".format(link_hours))

        # Quick batch generate
        st.markdown("---")
        with st.expander("📋 批量生成邀请链接"):
            batch_count = st.number_input("生成数量", min_value=1, max_value=50, value=5)
            batch_track = st.selectbox(
                "考核方向",
                [None] + list(TRACK_LABELS.keys()),
                format_func=lambda x: "候选人自选" if x is None else TRACK_LABELS[x],
                key="batch_track",
            )
            if st.button("批量生成"):
                user_id = st.session_state.get("user_id")
                base_url = "http://localhost:8502"
                links = []
                for _ in range(batch_count):
                    token = create_invite_link(track=batch_track, created_by=user_id, expires_hours=72)
                    links.append("{}/?invite={}".format(base_url, token))
                st.success("已生成 {} 条邀请链接：".format(batch_count))
                st.text_area("复制所有链接", value="\n".join(links), height=200)

    # ─── Tab 2: From Resume ───
    with tab_resume:
        candidates = get_all_candidates()

        if not candidates:
            st.info("暂无候选人，请先在「简历筛选」页面上传简历")
        else:
            candidate_options = {}
            for c in candidates:
                parsed = json.loads(c.get("parsed_data", "{}")) if isinstance(c.get("parsed_data"), str) else c.get("parsed_data", {})
                label = "{} ({})".format(parsed.get("name", c.get("name", "N/A")), c.get("resume_filename", ""))
                candidate_options[c["id"]] = label

            selected_candidate_id = st.selectbox(
                "选择候选人", list(candidate_options.keys()),
                format_func=lambda x: candidate_options[x], key="resume_candidate",
            )

            if selected_candidate_id:
                cand = next((c for c in candidates if c["id"] == selected_candidate_id), None)
                if cand:
                    parsed = json.loads(cand.get("parsed_data", "{}")) if isinstance(cand.get("parsed_data"), str) else cand.get("parsed_data", {})
                    info_cols = st.columns(4)
                    info_cols[0].markdown("**姓名**: {}".format(parsed.get("name", "N/A")))
                    edu = parsed.get("education", [])
                    if edu:
                        info_cols[1].markdown("**学校**: {}".format(edu[0].get("school", "N/A")))
                        info_cols[2].markdown("**学位**: {}".format(edu[0].get("degree", "N/A")))
                    exp = parsed.get("experience", [])
                    total_years = sum(e.get("years", 0) for e in exp)
                    info_cols[3].markdown("**工作年限**: {:.1f} 年".format(total_years))

                    if exp:
                        exp_strs = ["{} ({})".format(e.get("company", ""), e.get("title", "")) for e in exp[:3]]
                        st.markdown("**经历**: " + ", ".join(exp_strs))

            st.session_state["_entry_mode"] = "resume"
            st.session_state["_resume_candidate_id"] = selected_candidate_id if candidates else None

    # ─── Tab 3: Quick Entry ───
    with tab_manual:
        st.markdown("直接输入候选人信息，无需上传简历即可开始考试。")
        col1, col2 = st.columns(2)
        with col1:
            manual_name = st.text_input("姓名 *", placeholder="张三", key="manual_name")
            manual_school = st.text_input("学校", placeholder="清华大学", key="manual_school")
        with col2:
            manual_track = st.selectbox(
                "考核方向 *", list(TRACK_LABELS.keys()),
                format_func=lambda x: TRACK_LABELS[x], key="manual_track",
            )
            manual_domain = st.selectbox(
                "领域",
                ["Cross-Sectional (截面)", "Time-Series (时序)", "High-Frequency (高频)", "Alternative Data (另类数据)"],
                key="manual_domain",
            )
        st.session_state["_entry_mode"] = "manual"


# ═══════════════════════════════════════════
# CANDIDATE VIEW: Simple track selection
# ═══════════════════════════════════════════

elif _role == "candidate":
    st.markdown("### 欢迎参加 AI FLAB Research 面试考核")
    st.markdown("请选择考核方向，然后点击开始考试。")

    # Check if track was pre-assigned via invite
    invite_track = st.session_state.get("invite_track")
    if invite_track:
        st.info("已为您分配考核方向: **{}**".format(TRACK_LABELS.get(invite_track, invite_track)))


# ═══════════════════════════════════════════
# Track Selection Cards (visible for all roles)
# ═══════════════════════════════════════════

st.markdown("---")
st.subheader("选择考核方向并开始考试")

cols = st.columns(2)

for i, (track_key, track_label) in enumerate(TRACK_LABELS.items()):
    with cols[i % 2]:
        with st.container(border=True):
            st.markdown("### {}".format(track_label))
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

                if _role == "candidate":
                    # Candidate mode — use invite candidate ID
                    cid = st.session_state.get("invite_candidate_id")
                    if cid:
                        start_exam(cid, track_key, time_limit, 30)
                    else:
                        st.error("候选人信息缺失，请重新使用邀请链接")

                elif _role in ("admin", "operator"):
                    entry_mode = st.session_state.get("_entry_mode", "manual")

                    if entry_mode == "resume":
                        cid = st.session_state.get("_resume_candidate_id")
                        if not cid:
                            st.error("请先选择候选人")
                        else:
                            start_exam(cid, track_key, time_limit, 30)
                    else:
                        name = st.session_state.get("manual_name", "").strip()
                        if not name:
                            st.error("请输入候选人姓名")
                        else:
                            school = st.session_state.get("manual_school", "")
                            cid = insert_candidate_manual(name, school, track_key)
                            start_exam(cid, track_key, time_limit, 30)
