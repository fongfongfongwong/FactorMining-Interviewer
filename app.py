"""
FactorMining Interviewer — 量化团队简历筛选与面试考核系统
Stack: Streamlit + Claude API + PostgreSQL/SQLite + YAML Question Bank
"""

import os
import streamlit as st
from db.database import init_db
from services.auth import is_authenticated, get_current_role, logout, ensure_default_admin

# ─── Page Config ───
st.set_page_config(
    page_title="FactorMining Interviewer",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Initialize ───
init_db()
ensure_default_admin()

# ─── Sidebar ───
with st.sidebar:
    # Logo
    import base64
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.svg")
    if os.path.exists(logo_path):
        with open(logo_path, "r") as f:
            svg = f.read()
        b64 = base64.b64encode(svg.encode()).decode()
        st.markdown(
            '<img src="data:image/svg+xml;base64,{}" width="200" style="margin-bottom:8px"/>'.format(b64),
            unsafe_allow_html=True,
        )
    else:
        st.title("🎯 AI FLAB Research")
    st.caption("量化团队简历筛选与面试考核系统")
    st.divider()

    if is_authenticated():
        role = get_current_role()
        display = st.session_state.get("display_name", st.session_state.get("username", ""))

        if role == "candidate":
            st.markdown("👤 **候选人模式**")
        else:
            st.markdown("👤 **{}** ({})".format(display, role))

        # Role-based navigation guide
        if role == "admin":
            st.markdown("""
            ### 📌 导航
            - 📋 **简历筛选** — 上传简历，AI评分
            - 📝 **考试选择** — 选择考核方向
            - ⏱ **考试界面** — 计时答题
            - 📊 **成绩报告** — 分析与导出
            - ⚙ **管理后台** — 题库与系统
            - 👤 **用户管理** — 用户与邀请链接
            """)
        elif role == "operator":
            st.markdown("""
            ### 📌 导航
            - 📋 **简历筛选** — 上传简历，AI评分
            - 📝 **考试选择** — 选择考核方向
            - 📊 **成绩报告** — 查看结果
            """)
        else:  # candidate
            st.markdown("""
            ### 📌 导航
            - 📝 **考试选择** — 开始考试
            - ⏱ **考试界面** — 答题
            - 📊 **成绩报告** — 查看成绩
            """)

        st.divider()
        if st.button("🚪 退出登录"):
            logout()
            st.rerun()
    else:
        st.info("请先登录或使用邀请链接")

    st.divider()

    # API Key (admin only)
    if is_authenticated() and get_current_role() == "admin":
        current_key = st.session_state.get("anthropic_api_key", os.environ.get("ANTHROPIC_API_KEY", ""))
        if current_key:
            st.success("🔑 API: ***{}".format(current_key[-4:]))
        else:
            with st.expander("🔑 设置 API Key"):
                key_input = st.text_input("API Key", type="password", placeholder="sk-ant-api03-...", key="sidebar_api_key")
                if st.button("保存", key="sidebar_save_key"):
                    if key_input and key_input.startswith("sk-"):
                        os.environ["ANTHROPIC_API_KEY"] = key_input
                        st.session_state["anthropic_api_key"] = key_input
                        st.rerun()

    st.caption("Powered by Claude Opus 4.6")

# ─── Main Page ───
st.title("AI FLAB Research — Interviewer")
st.subheader("量化团队简历筛选与面试考核系统")

if not is_authenticated():
    st.markdown("---")
    st.info("👈 请先前往登录页面，或使用邀请链接进入考试")
    st.stop()

st.markdown("---")

role = get_current_role()

if role in ("admin", "operator"):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        ### 📋 简历筛选模块
        - 支持 PDF、DOCX 多文件上传
        - Claude AI 智能解析简历信息
        - 多维度加权评分
        - 四个岗位方向匹配度评分
        - 候选人排名与雷达图分析
        """)

    with col2:
        st.markdown("""
        ### 📝 面试考核模块
        四个考核方向，每个方向 100 道专业题：

        | 方向 | 考核内容 |
        |------|----------|
        | 量化开发 | 算法、系统设计、编程、并发 |
        | 量化研究 | 概率统计、因子建模、ML/DL |
        | 交易 | 微观结构、风险管理、做市 |
        | 组合经理 | 组合构建、风险归因、Alpha |

        + 10 道 IQ 智商题 + 5 道数学竞赛题
        """)

    st.markdown("---")

    from db.database import get_all_candidates, get_exam_sessions
    candidates = get_all_candidates()
    sessions = get_exam_sessions()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("候选人总数", len(candidates))
    m2.metric("已完成考试", len([s for s in sessions if s.get("status") == "completed"]))
    m3.metric("进行中考试", len([s for s in sessions if s.get("status") == "in_progress"]))
    completed = [s for s in sessions if s.get("status") == "completed"]
    avg = sum(s.get("total_score", 0) or 0 for s in completed) / max(1, len(completed)) if completed else 0
    m4.metric("平均分", "{:.1f}".format(avg) if completed else "N/A")

elif role == "candidate":
    st.markdown("### 欢迎参加 FactorMining 面试考核")
    st.markdown("请点击左侧「考试选择」开始考试。")
    if st.button("▶️ 开始考试", type="primary"):
        st.switch_page("pages/2_📝_Exam_Selection.py")
