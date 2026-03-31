"""成绩报告页面 — 分析、图表与导出"""

import json
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from db.database import (
    init_db, get_all_candidates, get_exam_sessions, get_exam_session,
    get_answers, get_candidate,
)
from services.exam_engine import TRACK_LABELS
from services.auth import is_authenticated, get_current_role
from utils.helpers import format_score

init_db()

st.set_page_config(page_title="成绩报告", page_icon="📊", layout="wide")

if not is_authenticated():
    st.warning("请先登录")
    st.stop()

st.title("📊 成绩报告 Results & Analytics")

# ─── Session Selection ───
sessions = get_exam_sessions()
completed = [s for s in sessions if s.get("status") == "completed"]

if not completed:
    # Check if just completed
    last_session = st.session_state.get("last_completed_session")
    if last_session:
        completed = [get_exam_session(last_session)]
        completed = [s for s in completed if s]

    if not completed:
        st.info("暂无已完成的考试记录")
        st.stop()

# Build session labels
session_options = {}
for s in completed:
    candidate = get_candidate(s["candidate_id"]) if s.get("candidate_id") else None
    name = "未知"
    if candidate:
        parsed = json.loads(candidate.get("parsed_data", "{}")) if isinstance(candidate.get("parsed_data"), str) else candidate.get("parsed_data", {})
        name = parsed.get("name", candidate.get("name", "未知"))
    track_label = TRACK_LABELS.get(s["track"], s["track"])
    score_str = f"{s.get('total_score', 0):.1f}/{s.get('max_score', 0):.0f}"
    session_options[s["id"]] = f"{name} — {track_label} — {score_str}"

selected_session_id = st.selectbox(
    "选择考试记录",
    list(session_options.keys()),
    format_func=lambda x: session_options[x],
)

if not selected_session_id:
    st.stop()

session = get_exam_session(selected_session_id)
answers_list = get_answers(selected_session_id)

if not session:
    st.error("考试记录未找到")
    st.stop()

# ─── Score Overview ───
st.markdown("---")
st.subheader("📈 总分概览")

total_score = session.get("total_score", 0) or 0
max_score = session.get("max_score", 0) or 1
pct = total_score / max_score * 100

col1, col2, col3, col4 = st.columns(4)
col1.metric("总分", f"{total_score:.1f}")
col2.metric("满分", f"{max_score:.0f}")
col3.metric("百分比", f"{pct:.1f}%")

# Grade
if pct >= 90:
    grade = "A+ 优秀"
elif pct >= 80:
    grade = "A 良好"
elif pct >= 70:
    grade = "B 合格"
elif pct >= 60:
    grade = "C 及格"
else:
    grade = "D 不及格"
col4.metric("等级", grade)

# ─── Category Breakdown ───
st.markdown("---")
st.subheader("📊 分类成绩")

breakdown = json.loads(session.get("score_breakdown", "{}")) if isinstance(session.get("score_breakdown"), str) else session.get("score_breakdown", {})

if breakdown:
    cat_data = []
    for cat, data in breakdown.items():
        cat_data.append({
            "类别": cat,
            "得分": data.get("score", 0),
            "满分": data.get("max", 0),
            "题数": data.get("count", 0),
            "正确数": data.get("correct", 0),
            "正确率": f"{data.get('correct', 0) / max(1, data.get('count', 1)) * 100:.0f}%",
            "得分率": data.get("score", 0) / max(0.01, data.get("max", 1)) * 100,
        })

    df_cat = pd.DataFrame(cat_data)
    st.dataframe(df_cat, use_container_width=True, hide_index=True)

    # Bar chart
    fig = px.bar(
        df_cat,
        x="类别",
        y="得分率",
        color="得分率",
        color_continuous_scale=["#EF553B", "#FFA15A", "#00CC96"],
        title="各类别得分率 (%)",
        labels={"得分率": "得分率 (%)"},
    )
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    # Radar chart
    if len(cat_data) >= 3:
        fig_radar = go.Figure()
        cats = [d["类别"] for d in cat_data]
        vals = [d["得分率"] for d in cat_data]
        fig_radar.add_trace(go.Scatterpolar(
            r=vals + [vals[0]],
            theta=cats + [cats[0]],
            fill="toself",
            name="得分率",
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            title="能力雷达图",
            height=500,
        )
        st.plotly_chart(fig_radar, use_container_width=True)

# ─── Answer Details ───
st.markdown("---")
st.subheader("📝 答题详情")

if answers_list:
    for ans in answers_list:
        is_correct = ans.get("is_correct", 0)
        icon = "✅" if is_correct else "❌"
        score = ans.get("score", 0)
        max_s = ans.get("max_score", 1)

        with st.expander(f"{icon} {ans.get('question_id', 'N/A')} — {score:.1f}/{max_s:.0f}"):
            st.markdown(f"**回答**: {ans.get('response', '未作答')[:500]}")
            if ans.get("grading_notes"):
                st.markdown(f"**评分说明**: {ans.get('grading_notes', '')[:500]}")
else:
    st.info("暂无答题详情")

# ─── Export ───
st.markdown("---")
if answers_list:
    export_data = []
    for ans in answers_list:
        export_data.append({
            "题目ID": ans.get("question_id", ""),
            "回答": ans.get("response", ""),
            "得分": ans.get("score", 0),
            "满分": ans.get("max_score", 0),
            "是否正确": "是" if ans.get("is_correct") else "否",
            "评分说明": ans.get("grading_notes", ""),
        })
    df_export = pd.DataFrame(export_data)
    csv = df_export.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 导出答题详情CSV", csv, f"exam_results_{selected_session_id}.csv", "text/csv")
