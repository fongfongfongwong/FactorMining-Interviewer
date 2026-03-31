"""简历筛选页面 — 批量上传简历，AI解析评分，生成考试邀请链接"""

import json
import streamlit as st
import plotly.graph_objects as go

from db.database import (
    init_db, insert_candidate, get_all_candidates, delete_candidate,
    create_invite_link, get_exam_sessions,
)
from services.resume_parser import extract_text, parse_resume_with_claude
from services.scoring import calculate_scores, ROLE_LABELS
from services.exam_engine import TRACK_LABELS
from utils.helpers import candidates_to_dataframe, export_candidates_csv
from services.auth import require_role, is_authenticated

init_db()

st.set_page_config(page_title="简历筛选", page_icon="📋", layout="wide")

if not is_authenticated():
    st.warning("请先登录 / Please login first")
    st.stop()
require_role("admin", "operator")

st.title("📋 简历筛选 Resume Screening")

# ═══════════════════════════════════════════
# Section 1: Batch Upload
# ═══════════════════════════════════════════
st.subheader("📤 批量上传简历 Batch Upload")

uploaded_files = st.file_uploader(
    "拖拽或选择多份简历文件（PDF / DOCX），支持一次上传整个文件夹",
    type=["pdf", "docx", "txt"],
    accept_multiple_files=True,
)

if uploaded_files:
    st.info("已选择 **{}** 份简历，点击下方按钮开始AI解析".format(len(uploaded_files)))

    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        start_parse = st.button(
            "🚀 开始批量解析 ({} 份)".format(len(uploaded_files)),
            type="primary",
        )

    if start_parse:
        progress = st.progress(0, text="准备中...")
        success_count = 0
        fail_count = 0

        for i, uploaded_file in enumerate(uploaded_files):
            progress.progress(
                i / len(uploaded_files),
                text="正在解析 {} ({}/{})...".format(uploaded_file.name, i + 1, len(uploaded_files)),
            )

            try:
                file_bytes = uploaded_file.read()
                resume_text = extract_text(uploaded_file.name, file_bytes)

                if len(resume_text.strip()) < 50:
                    st.warning("⚠️ {} 提取的文本过短，跳过".format(uploaded_file.name))
                    fail_count += 1
                    continue

                with st.spinner("🤖 AI解析 {}...".format(uploaded_file.name)):
                    parsed = parse_resume_with_claude(resume_text)

                if "error" in parsed:
                    st.error("❌ {} 解析失败".format(uploaded_file.name))
                    fail_count += 1
                    continue

                scores = calculate_scores(parsed)

                insert_candidate(
                    name=parsed.get("name", "未知"),
                    email=parsed.get("email", ""),
                    phone=parsed.get("phone", ""),
                    resume_filename=uploaded_file.name,
                    resume_text=resume_text,
                    parsed_data=parsed,
                    scores=scores,
                )

                success_count += 1

            except Exception as e:
                st.error("❌ {} 出错: {}".format(uploaded_file.name, str(e)))
                fail_count += 1

        progress.progress(1.0, text="批量解析完成！")
        st.success("✅ 成功: {} 份 | ❌ 失败: {} 份".format(success_count, fail_count))
        st.rerun()

# ═══════════════════════════════════════════
# Section 2: Candidate Dashboard
# ═══════════════════════════════════════════
st.markdown("---")
st.subheader("📊 候选人管理 Candidate Dashboard")

candidates = get_all_candidates()

if not candidates:
    st.info("暂无候选人数据，请上传简历开始筛选")
    st.stop()

# Sort controls
sort_role = st.selectbox(
    "按岗位匹配度排序",
    list(ROLE_LABELS.keys()),
    format_func=lambda x: ROLE_LABELS[x],
)


def get_role_score(c):
    scores = json.loads(c.get("scores", "{}")) if isinstance(c.get("scores"), str) else c.get("scores", {})
    return scores.get(sort_role, {}).get("total", 0)


candidates_sorted = sorted(candidates, key=get_role_score, reverse=True)

# Display as dataframe
df = candidates_to_dataframe(candidates_sorted)
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "量化开发": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
        "量化研究": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
        "交易员": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
        "组合经理": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
        "最高分": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
    },
)

# Export
csv_data = export_candidates_csv(candidates_sorted)
st.download_button("📥 导出CSV", csv_data, "candidates_report.csv", "text/csv")

# ═══════════════════════════════════════════
# Section 3: Per-candidate detail + invite link
# ═══════════════════════════════════════════
st.markdown("---")
st.subheader("🔍 候选人详情 & 考试邀请")

selected_id = st.selectbox(
    "选择候选人",
    [c["id"] for c in candidates_sorted],
    format_func=lambda x: next(
        ("{} ({})".format(
            json.loads(c.get("parsed_data", "{}")).get("name", c.get("name", "N/A")),
            c.get("resume_filename", ""))
         for c in candidates_sorted if c["id"] == x),
        str(x),
    ),
)

if selected_id:
    candidate = next((c for c in candidates_sorted if c["id"] == selected_id), None)
    if candidate:
        parsed = json.loads(candidate.get("parsed_data", "{}")) if isinstance(candidate.get("parsed_data"), str) else candidate.get("parsed_data", {})
        scores = json.loads(candidate.get("scores", "{}")) if isinstance(candidate.get("scores"), str) else candidate.get("scores", {})

        # ── Info + Invite Link side by side ──
        col_info, col_invite = st.columns([3, 2])

        with col_info:
            st.markdown("#### 基本信息")
            st.markdown("**姓名**: {}".format(parsed.get("name", "N/A")))
            st.markdown("**邮箱**: {}".format(parsed.get("email", "N/A")))
            st.markdown("**电话**: {}".format(parsed.get("phone", "N/A")))
            st.markdown("**总结**: {}".format(parsed.get("summary", "N/A")))

            if parsed.get("education"):
                st.markdown("**教育背景**:")
                for edu in parsed["education"]:
                    gpa_str = " (GPA: {})".format(edu.get("gpa")) if edu.get("gpa") else ""
                    st.markdown("- {} | {} {}{}".format(
                        edu.get("school", "N/A"), edu.get("degree", ""), edu.get("major", ""), gpa_str))

            if parsed.get("skills"):
                st.markdown("**技能**: {}".format(", ".join(parsed["skills"][:20])))

            if parsed.get("competitions"):
                st.markdown("**竞赛**:")
                for comp in parsed["competitions"]:
                    st.markdown("- {} — {}".format(comp.get("name", "N/A"), comp.get("rank", "N/A")))

            # Exam history
            sessions = get_exam_sessions(selected_id)
            if sessions:
                st.markdown("**考试记录**:")
                for s in sessions:
                    icon = "✅" if s["status"] == "completed" else "⏳"
                    score_str = " — {:.1f}/{:.0f}".format(s.get("total_score", 0) or 0, s.get("max_score", 0) or 0) if s["status"] == "completed" else ""
                    st.markdown("- {} {}{}".format(icon, TRACK_LABELS.get(s["track"], s["track"]), score_str))

        with col_invite:
            st.markdown("#### 🔗 生成考试邀请链接")

            inv_track = st.selectbox(
                "考核方向",
                [None] + list(TRACK_LABELS.keys()),
                format_func=lambda x: "候选人自选" if x is None else TRACK_LABELS[x],
                key="inv_track_{}".format(selected_id),
            )
            inv_hours = st.number_input("有效期（小时）", min_value=1, max_value=720, value=72,
                                        key="inv_hours_{}".format(selected_id))

            if st.button("🔗 生成邀请链接", key="gen_invite_{}".format(selected_id), type="primary"):
                user_id = st.session_state.get("user_id")
                token = create_invite_link(
                    candidate_name=parsed.get("name", ""),
                    candidate_email=parsed.get("email", ""),
                    track=inv_track,
                    created_by=user_id,
                    expires_hours=inv_hours,
                )
                base_url = st.session_state.get("base_url", "http://localhost:8502")
                invite_url = "{}/?invite={}".format(base_url, token)
                st.success("邀请链接已生成！")
                st.code(invite_url, language=None)
                st.caption("有效期 {} 小时，候选人打开链接即可开始考试".format(inv_hours))

            # Quick invite for best-fit role
            if scores:
                best_role = max(scores.items(), key=lambda x: x[1].get("total", 0) if isinstance(x[1], dict) else 0)
                st.caption("💡 最佳匹配: {} ({:.1f}分)".format(
                    best_role[1].get("label", ""), best_role[1].get("total", 0)))

        # ── Radar chart ──
        st.markdown("---")
        if scores:
            categories = ["教育", "竞赛", "技能", "经验", "研究"]
            fig = go.Figure()
            for role_key, role_data in scores.items():
                if not isinstance(role_data, dict):
                    continue
                dims = role_data.get("dimensions", {})
                values = [
                    dims.get("education", 0),
                    dims.get("competitions", 0),
                    dims.get("skills", 0),
                    dims.get("experience", 0),
                    dims.get("research", 0),
                ]
                fig.add_trace(go.Scatterpolar(
                    r=values + [values[0]],
                    theta=categories + [categories[0]],
                    fill="toself",
                    name="{} ({:.1f})".format(role_data.get("label", role_key), role_data.get("total", 0)),
                    opacity=0.6,
                ))

            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                showlegend=True,
                title="岗位匹配度雷达图",
                height=450,
            )
            st.plotly_chart(fig, use_container_width=True)

        # Delete
        if st.button("🗑️ 删除该候选人", type="secondary"):
            delete_candidate(selected_id)
            st.success("已删除")
            st.rerun()
