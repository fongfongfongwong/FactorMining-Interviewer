"""考试界面 — 计时答题"""

import time
import streamlit as st

from db.database import init_db, save_answer, finish_exam_session, update_exam_progress
from services.exam_engine import grade_question, TRACK_LABELS
from services.auth import is_authenticated
from utils.helpers import seconds_to_hms

init_db()

st.set_page_config(page_title="考试界面", page_icon="⏱", layout="wide")

if not is_authenticated():
    st.warning("请先登录或使用邀请链接")
    st.stop()

# ─── Check exam session ───
if "exam_session_id" not in st.session_state:
    st.title("⏱ 考试界面")
    st.warning("没有进行中的考试，请先在「考试选择」页面创建考试")
    st.stop()

session_id = st.session_state["exam_session_id"]
questions = st.session_state["exam_questions"]
track = st.session_state["exam_track"]
current_q = st.session_state.get("exam_current_q", 0)
answers = st.session_state.get("exam_answers", {})
start_time = st.session_state.get("exam_start_time", time.time())
time_limit = st.session_state.get("exam_time_limit", 7200)

# ─── Timer ───
elapsed = int(time.time() - start_time)
remaining = max(0, time_limit - elapsed)

# Check timeout
if remaining <= 0:
    st.error("⏰ 考试时间已到！正在自动提交...")
    # Auto-submit will be handled below

# ─── Header ───
st.title(f"⏱ {TRACK_LABELS.get(track, track)}")

header_cols = st.columns([2, 1, 1, 1])
with header_cols[0]:
    st.progress(len(answers) / len(questions), text=f"进度: {len(answers)}/{len(questions)}")
with header_cols[1]:
    color = "🔴" if remaining < 300 else "🟡" if remaining < 600 else "🟢"
    st.markdown(f"### {color} {seconds_to_hms(remaining)}")
with header_cols[2]:
    st.metric("已答", len(answers))
with header_cols[3]:
    st.metric("总题数", len(questions))

st.markdown("---")

# ─── Submit handler ───
def submit_exam():
    """Grade all answers and finish session."""
    total_score = 0
    max_score = 0
    category_scores = {}

    for idx, q in enumerate(questions):
        response = answers.get(idx, "")
        q_id = q.get("id", f"q_{idx}")
        points = q.get("points", 1.0)
        category = q.get("category", "unknown")

        if response:
            is_correct, score, notes = grade_question(q, response)
        else:
            is_correct, score, notes = False, 0, "未作答"

        save_answer(session_id, q_id, response, is_correct, score, points, notes)
        total_score += score
        max_score += points

        if category not in category_scores:
            category_scores[category] = {"score": 0, "max": 0, "count": 0, "correct": 0}
        category_scores[category]["score"] += score
        category_scores[category]["max"] += points
        category_scores[category]["count"] += 1
        if is_correct:
            category_scores[category]["correct"] += 1

    finish_exam_session(session_id, total_score, max_score, category_scores)

    # Clean up session state
    for key in ["exam_session_id", "exam_questions", "exam_track", "exam_current_q",
                "exam_answers", "exam_time_limit", "exam_start_time", "exam_candidate_id"]:
        st.session_state.pop(key, None)

    st.session_state["last_completed_session"] = session_id
    return total_score, max_score

# Auto-submit on timeout
if remaining <= 0:
    total, mx = submit_exam()
    st.success(f"考试已自动提交！得分: {total:.1f}/{mx:.0f}")
    st.switch_page("pages/4_📊_Results.py")

# ─── Question Navigation ───
nav_cols = st.columns([1, 6, 1])

with nav_cols[0]:
    if st.button("⬅ 上一题", disabled=current_q <= 0):
        st.session_state["exam_current_q"] = current_q - 1
        st.rerun()

with nav_cols[2]:
    if current_q < len(questions) - 1:
        if st.button("下一题 ➡"):
            st.session_state["exam_current_q"] = current_q + 1
            st.rerun()

# Quick jump
with st.expander("📋 题目导航 (点击跳转)"):
    jump_cols = st.columns(15)
    for idx in range(len(questions)):
        col = jump_cols[idx % 15]
        status = "✅" if idx in answers else "⬜"
        if col.button(f"{status}{idx+1}", key=f"jump_{idx}"):
            st.session_state["exam_current_q"] = idx
            st.rerun()

st.markdown("---")

# ─── Current Question ───
if current_q < len(questions):
    q = questions[current_q]
    q_type = q.get("type", "multiple_choice")
    difficulty = q.get("difficulty", "medium_high")
    category = q.get("category", "")
    diff_labels = {"medium_high": "🟡 中高", "senior": "🟠 资深", "expert": "🔴 专家"}

    st.markdown(f"### 第 {current_q + 1} 题 / {len(questions)}")
    st.caption(f"类别: {category} | 难度: {diff_labels.get(difficulty, difficulty)} | 分值: {q.get('points', 1)}")

    st.markdown(q.get("question", "题目缺失"))

    # Code block if present
    if q.get("code_snippet"):
        st.code(q["code_snippet"], language=q.get("code_language", "python"))

    # Answer input — all questions are 5-option multiple choice (A-E)
    existing_answer = answers.get(current_q, "")

    options = q.get("options", [])
    if not options:
        options = ["A", "B", "C", "D", "E"]

    # Build option labels with letter prefix if not already present
    option_labels = []
    for i, opt in enumerate(options):
        opt_str = str(opt)
        if opt_str.startswith(("{}.".format(chr(65+i)), "{} ".format(chr(65+i)))):
            option_labels.append(opt_str)
        else:
            option_labels.append("{}. {}".format(chr(65+i), opt_str))

    # Find existing selection index
    existing_idx = None
    if existing_answer:
        for i, opt in enumerate(options):
            if existing_answer == chr(65+i) or existing_answer == str(i+1):
                existing_idx = i
                break

    selected = st.radio(
        "选择答案 Select your answer",
        option_labels,
        index=existing_idx,
        key="answer_{}".format(current_q),
    )

    if selected:
        letter = selected[0]
        answers[current_q] = letter
        st.session_state["exam_answers"] = answers

# ─── Save progress to DB on every render ───
if answers:
    update_exam_progress(session_id, current_q, {str(k): v for k, v in answers.items()})

# ─── Submit Button ───
st.markdown("---")
unanswered = len(questions) - len(answers)
if unanswered > 0:
    st.warning(f"还有 {unanswered} 道题未作答")

if st.button("📨 提交考试", type="primary"):
    with st.spinner("正在评分中...请稍候"):
        total, mx = submit_exam()
    st.success(f"🎉 考试提交成功！得分: {total:.1f}/{mx:.0f}")
    st.balloons()
    st.switch_page("pages/4_📊_Results.py")
