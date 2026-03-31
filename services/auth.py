"""Authentication service — password auth for admin/operator, invite links for candidates."""

import os
import bcrypt
import streamlit as st
from db.database import get_user_by_username, create_user, get_invite_link, mark_invite_used, log_audit

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def login(username, password):
    """Authenticate admin/operator. Returns user dict or None."""
    user = get_user_by_username(username)
    if user and verify_password(password, user["password_hash"]):
        st.session_state["authenticated"] = True
        st.session_state["user_id"] = user["id"]
        st.session_state["username"] = user["username"]
        st.session_state["user_role"] = user["role"]
        st.session_state["display_name"] = user.get("display_name", user["username"])
        log_audit("login", user_id=user["id"], details={"username": username})
        return user
    return None


def logout():
    """Clear session."""
    user_id = st.session_state.get("user_id")
    if user_id:
        log_audit("logout", user_id=user_id)
    for key in ["authenticated", "user_id", "username", "user_role", "display_name",
                "candidate_mode", "invite_token", "invite_candidate_id"]:
        st.session_state.pop(key, None)


def validate_invite(token):
    """Validate an invite link token. Returns invite dict or None."""
    invite = get_invite_link(token)
    if not invite:
        return None
    if invite.get("used_at"):
        return None
    expires = invite.get("expires_at", "")
    if expires:
        from datetime import datetime
        try:
            exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00")) if isinstance(expires, str) else expires
            if exp_dt < datetime.utcnow():
                return None
        except (ValueError, TypeError):
            pass
    return invite


def enter_candidate_mode(token, candidate_id):
    """Set session state for candidate access via invite link."""
    st.session_state["authenticated"] = True
    st.session_state["user_role"] = "candidate"
    st.session_state["candidate_mode"] = True
    st.session_state["invite_token"] = token
    st.session_state["invite_candidate_id"] = candidate_id
    mark_invite_used(token)
    log_audit("candidate_enter", details={"token": token, "candidate_id": candidate_id})


def is_authenticated():
    return st.session_state.get("authenticated", False)


def get_current_role():
    return st.session_state.get("user_role", None)


def require_role(*allowed_roles):
    """Block access if current user's role is not in allowed_roles."""
    if not is_authenticated():
        st.error("请先登录 / Please login first")
        st.stop()
    role = get_current_role()
    if role not in allowed_roles:
        st.error("权限不足 / Access denied")
        st.stop()


def ensure_default_admin():
    """Create default users if no users exist."""
    from db.database import get_all_users
    users = get_all_users()
    if not users:
        create_user("admin", hash_password("admin123"), "admin", "管理员")
        create_user("sisi", hash_password("hello456"), "admin", "Sisi")
