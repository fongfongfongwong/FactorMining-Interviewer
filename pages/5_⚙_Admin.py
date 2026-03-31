"""管理后台 — 题库管理与系统数据"""

import os
import json
import streamlit as st
import yaml
import pandas as pd

from db.database import init_db, get_all_candidates, get_exam_sessions
from services.exam_engine import TRACK_LABELS, TRACK_FILES, QUESTIONS_DIR, load_track_questions, load_shared_questions
from services.auth import require_role, is_authenticated

init_db()

st.set_page_config(page_title="管理后台", page_icon="⚙", layout="wide")

if not is_authenticated():
    st.warning("请先登录")
    st.stop()
require_role("admin")

st.title("⚙ 管理后台 Admin Panel")

tab1, tab2, tab3 = st.tabs(["📚 题库概览", "📊 统计面板", "🔧 系统设置"])

# ─── Tab 1: Question Bank Overview ───
with tab1:
    st.subheader("题库概览")

    for track_key, track_label in TRACK_LABELS.items():
        questions = load_track_questions(track_key)
        with st.expander(f"📋 {track_label} — {len(questions)} 道题", expanded=False):
            if not questions:
                st.warning("题库为空")
                continue

            # Difficulty distribution
            diff_counts = {}
            type_counts = {}
            cat_counts = {}
            for q in questions:
                d = q.get("difficulty", "unknown")
                t = q.get("type", "unknown")
                c = q.get("category", "unknown")
                diff_counts[d] = diff_counts.get(d, 0) + 1
                type_counts[t] = type_counts.get(t, 0) + 1
                cat_counts[c] = cat_counts.get(c, 0) + 1

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**难度分布**")
                diff_labels = {"medium_high": "中高", "senior": "资深", "expert": "专家"}
                for k, v in sorted(diff_counts.items()):
                    st.markdown(f"- {diff_labels.get(k, k)}: {v}")
            with col2:
                st.markdown("**题型分布**")
                type_labels = {"multiple_choice": "选择题", "code": "编程题", "open_ended": "开放题", "show_work": "推导题"}
                for k, v in sorted(type_counts.items()):
                    st.markdown(f"- {type_labels.get(k, k)}: {v}")
            with col3:
                st.markdown("**类别分布**")
                for k, v in sorted(cat_counts.items()):
                    st.markdown(f"- {k}: {v}")

            # Sample questions
            st.markdown("**示例题目 (前5题)**")
            for q in questions[:5]:
                st.markdown(f"- [{q.get('difficulty', '?')}] {q.get('question', '?')[:100]}...")

    # Shared questions
    shared = load_shared_questions()
    iq_qs = [q for q in shared if q.get("category") == "iq_brainteaser"]
    math_qs = [q for q in shared if q.get("category") == "math_competition"]

    with st.expander(f"🧠 IQ/智商题 — {len(iq_qs)} 道", expanded=False):
        for q in iq_qs[:5]:
            st.markdown(f"- {q.get('question', '?')[:100]}...")

    with st.expander(f"📐 数学竞赛题 — {len(math_qs)} 道", expanded=False):
        for q in math_qs[:5]:
            st.markdown(f"- {q.get('question', '?')[:100]}...")

# ─── Tab 2: Statistics ───
with tab2:
    st.subheader("系统统计")

    candidates = get_all_candidates()
    sessions = get_exam_sessions()
    completed_sessions = [s for s in sessions if s.get("status") == "completed"]

    col1, col2, col3 = st.columns(3)
    col1.metric("候选人总数", len(candidates))
    col2.metric("考试总数", len(sessions))
    col3.metric("已完成考试", len(completed_sessions))

    if completed_sessions:
        st.markdown("---")
        st.markdown("**成绩分布**")

        scores = [s.get("total_score", 0) or 0 for s in completed_sessions]
        max_scores = [s.get("max_score", 1) or 1 for s in completed_sessions]
        pcts = [s / m * 100 for s, m in zip(scores, max_scores)]

        import plotly.express as px
        fig = px.histogram(x=pcts, nbins=10, title="考试成绩分布", labels={"x": "得分率 (%)", "count": "人数"})
        st.plotly_chart(fig, use_container_width=True)

        # Per-track stats
        track_stats = {}
        for s in completed_sessions:
            track = s.get("track", "unknown")
            if track not in track_stats:
                track_stats[track] = {"scores": [], "count": 0}
            pct_val = (s.get("total_score", 0) or 0) / max((s.get("max_score", 1) or 1), 0.01) * 100
            track_stats[track]["scores"].append(pct_val)
            track_stats[track]["count"] += 1

        stat_rows = []
        for track, data in track_stats.items():
            import statistics
            stat_rows.append({
                "方向": TRACK_LABELS.get(track, track),
                "考试人数": data["count"],
                "平均分(%)": f"{statistics.mean(data['scores']):.1f}",
                "最高分(%)": f"{max(data['scores']):.1f}",
                "最低分(%)": f"{min(data['scores']):.1f}",
            })

        if stat_rows:
            st.dataframe(pd.DataFrame(stat_rows), use_container_width=True, hide_index=True)

# ─── Tab 3: Settings ───
with tab3:
    st.subheader("系统设置")

    st.markdown("**题库文件路径**")
    st.code(QUESTIONS_DIR)

    st.markdown("**数据库路径**")
    from db.database import DB_PATH
    st.code(DB_PATH)

    if os.path.exists(DB_PATH):
        st.markdown(f"数据库大小: {os.path.getsize(DB_PATH) / 1024:.1f} KB")

    st.markdown("---")
    st.markdown("**API Key 设置**")

    # Load saved key from session state or environment
    current_key = st.session_state.get("anthropic_api_key", os.environ.get("ANTHROPIC_API_KEY", ""))

    api_key_input = st.text_input(
        "ANTHROPIC_API_KEY",
        value=current_key,
        type="password",
        placeholder="sk-ant-api03-...",
        help="输入你的 Anthropic API Key，用于简历解析和开放题评分",
    )

    if st.button("💾 保存 API Key", type="primary"):
        if api_key_input and api_key_input.startswith("sk-"):
            os.environ["ANTHROPIC_API_KEY"] = api_key_input
            st.session_state["anthropic_api_key"] = api_key_input
            # Clear cached client so it picks up the new key
            from services.claude_client import get_client
            get_client.clear()
            st.success(f"✅ API Key 已保存 (***{api_key_input[-4:]})")
        else:
            st.error("❌ 请输入有效的 API Key（以 sk- 开头）")

    st.markdown("**API 状态**")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "") or st.session_state.get("anthropic_api_key", "")
    if api_key:
        st.success(f"✅ ANTHROPIC_API_KEY 已设置 (***{api_key[-4:]})")
    else:
        st.warning("⚠️ ANTHROPIC_API_KEY 未设置 — 简历AI解析和开放题评分功能不可用，选择题评分仍可正常使用")

    st.markdown("---")
    if st.button("🗑️ 清空所有数据", type="secondary"):
        st.warning("⚠️ 此操作将删除所有候选人和考试数据，无法恢复！")
        if st.button("确认清空", type="primary"):
            import sqlite3
            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
                init_db()
                st.success("数据已清空")
                st.rerun()
