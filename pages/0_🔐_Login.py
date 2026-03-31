"""登录页面 — Admin/Operator password login, Candidate invite link entry."""

import sys
import streamlit as st

st.set_page_config(page_title="登录", page_icon="🔐", layout="centered")

from db.database import init_db
from services.auth import login, logout, is_authenticated, get_current_role, validate_invite, enter_candidate_mode, ensure_default_admin

init_db()
ensure_default_admin()

# ─── Handle invite link from URL ───
query_params = st.query_params
invite_token = query_params.get("invite", None)

if invite_token and not is_authenticated():
    invite = validate_invite(invite_token)
    if invite:
        st.title("🎯 FactorMining 面试考核")
        st.success("邀请链接有效！请填写信息开始考试。")

        with st.form("invite_form"):
            name = st.text_input("姓名 *", value=invite.get("candidate_name", ""))
            email = st.text_input("邮箱", value=invite.get("candidate_email", ""))
            school = st.text_input("学校")
            track_display = invite.get("track", "")

            if track_display:
                from services.exam_engine import TRACK_LABELS
                st.info("已分配考核方向: {}".format(TRACK_LABELS.get(track_display, track_display)))

            submitted = st.form_submit_button("进入考试", type="primary")

            if submitted:
                if not name.strip():
                    st.error("请输入姓名")
                else:
                    from db.database import insert_candidate_manual
                    cid = insert_candidate_manual(name.strip(), school, track_display or "")
                    enter_candidate_mode(invite_token, cid)
                    st.session_state["invite_track"] = invite.get("track")
                    st.rerun()
    else:
        st.error("邀请链接无效或已过期 / Invalid or expired invite link")

# ─── Already authenticated ───
if is_authenticated():
    role = get_current_role()
    st.title("🔐 已登录")

    if role == "candidate":
        st.success("候选人模式 — 请前往考试页面")
        if st.button("开始考试 ➡️", type="primary"):
            st.switch_page("pages/2_📝_Exam_Selection.py")
    else:
        st.success("欢迎, {} ({})".format(
            st.session_state.get("display_name", ""),
            role,
        ))
        st.markdown("请从左侧菜单选择功能模块。")

    if st.button("退出登录"):
        logout()
        st.rerun()
    st.stop()

# ─── Login form ───
st.title("🔐 登录 Login")
st.caption("管理人员请输入用户名和密码登录")

with st.form("login_form"):
    username = st.text_input("用户名")
    password = st.text_input("密码", type="password")
    submitted = st.form_submit_button("登录", type="primary")

    if submitted:
        if not username or not password:
            st.error("请输入用户名和密码")
        else:
            try:
                user = login(username, password)
                if user:
                    st.success("登录成功！")
                    st.rerun()
                else:
                    st.error("用户名或密码错误")
            except Exception as e:
                st.error("登录异常: {}".format(str(e)))

st.markdown("---")
st.caption("默认管理员: admin / admin123 (请登录后立即修改密码)")

# Debug info (remove in production)
with st.expander("🔧 Debug Info"):
    try:
        from db.database import get_all_users, DB_PATH, USE_PG
        users = get_all_users()
        st.markdown("**DB**: {} ({})".format("PostgreSQL" if USE_PG else "SQLite", DB_PATH if not USE_PG else "remote"))
        st.markdown("**Users**: {}".format([(u["username"], u["role"]) for u in users]))
        st.markdown("**Python**: {}".format(sys.version))
    except Exception as e:
        st.error("Debug error: {}".format(str(e)))
