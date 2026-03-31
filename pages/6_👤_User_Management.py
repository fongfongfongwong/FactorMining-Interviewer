"""用户管理 — Admin only: manage users, create invite links, view audit log."""

import streamlit as st
st.set_page_config(page_title="用户管理", page_icon="👤", layout="wide")

from db.database import (
    init_db, get_all_users, create_user, deactivate_user,
    create_invite_link, get_all_invite_links, get_audit_log,
)
from services.auth import require_role, hash_password, is_authenticated
from services.exam_engine import TRACK_LABELS

init_db()



if not is_authenticated():
    st.warning("请先登录")
    st.stop()

require_role("admin")

st.title("👤 用户管理 User Management")

tab_users, tab_invites, tab_audit = st.tabs(["👥 用户列表", "🔗 邀请链接", "📋 审计日志"])

# ─── Tab 1: Users ───
with tab_users:
    st.subheader("管理用户")

    # Add user form
    with st.expander("➕ 添加用户", expanded=False):
        with st.form("add_user"):
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input("用户名 *")
                new_password = st.text_input("密码 *", type="password")
            with col2:
                new_role = st.selectbox("角色 *", ["operator", "admin"])
                new_display = st.text_input("显示名称")

            if st.form_submit_button("创建用户", type="primary"):
                if not new_username or not new_password:
                    st.error("请填写用户名和密码")
                else:
                    try:
                        create_user(new_username, hash_password(new_password), new_role, new_display)
                        st.success("用户 {} 创建成功".format(new_username))
                        st.rerun()
                    except Exception as e:
                        st.error("创建失败: {}".format(str(e)))

    # User list
    users = get_all_users()
    if users:
        for u in users:
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            col1.markdown("**{}** ({})".format(u.get("username", ""), u.get("display_name", "")))
            col2.markdown(u.get("role", ""))
            active = u.get("is_active", True)
            col3.markdown("✅ 活跃" if active else "❌ 已停用")
            if active and u.get("username") != "admin":
                if col4.button("停用", key="deact_{}".format(u["id"])):
                    deactivate_user(u["id"])
                    st.rerun()
    else:
        st.info("暂无用户")

# ─── Tab 2: Invite Links ───
with tab_invites:
    st.subheader("候选人邀请链接")
    st.markdown("创建邀请链接发送给候选人，候选人通过链接直接进入考试，无需注册登录。")

    with st.expander("➕ 创建邀请链接", expanded=True):
        with st.form("create_invite"):
            col1, col2 = st.columns(2)
            with col1:
                inv_name = st.text_input("候选人姓名（可选）")
                inv_email = st.text_input("候选人邮箱（可选）")
            with col2:
                inv_track = st.selectbox(
                    "预分配考核方向（可选）",
                    [None] + list(TRACK_LABELS.keys()),
                    format_func=lambda x: "候选人自选" if x is None else TRACK_LABELS[x],
                )
                inv_hours = st.number_input("链接有效期（小时）", min_value=1, max_value=720, value=72)

            if st.form_submit_button("生成邀请链接", type="primary"):
                user_id = st.session_state.get("user_id")
                token = create_invite_link(
                    candidate_name=inv_name,
                    candidate_email=inv_email,
                    track=inv_track,
                    created_by=user_id,
                    expires_hours=inv_hours,
                )
                # Build the invite URL
                base_url = st.session_state.get("base_url", "http://localhost:8502")
                invite_url = "{}/?invite={}".format(base_url, token)
                st.success("邀请链接已生成！")
                st.code(invite_url, language=None)
                st.info("请将此链接发送给候选人。链接有效期 {} 小时。".format(inv_hours))

    # Existing links
    st.markdown("---")
    st.markdown("**已创建的邀请链接**")
    links = get_all_invite_links()
    if links:
        for link in links:
            status = "✅ 已使用" if link.get("used_at") else "⏳ 待使用"
            name = link.get("candidate_name", "未指定")
            track = TRACK_LABELS.get(link.get("track", ""), "自选")
            token = link.get("token", "")[:8] + "..."
            st.markdown("- {} | {} | {} | Token: `{}`".format(status, name, track, token))
    else:
        st.info("暂无邀请链接")

# ─── Tab 3: Audit Log ───
with tab_audit:
    st.subheader("审计日志")
    logs = get_audit_log(limit=200)
    if logs:
        import pandas as pd
        df = pd.DataFrame(logs)
        display_cols = ["timestamp", "action", "user_id", "resource_type", "resource_id"]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available], use_container_width=True, hide_index=True)
    else:
        st.info("暂无日志")
