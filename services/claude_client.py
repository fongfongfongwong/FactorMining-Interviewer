"""Anthropic Claude client singleton with prompt caching."""

import os
import streamlit as st
import anthropic

MODEL = "claude-opus-4-6"
MAX_TOKENS = 8192


@st.cache_resource
def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY", None) if hasattr(st, "secrets") else None
        except Exception:
            pass
    if not api_key:
        st.warning("⚠️ ANTHROPIC_API_KEY 未配置。简历AI解析和开放题评分不可用，选择题评分正常。请在 Streamlit Cloud > Settings > Secrets 中添加。")
        return None
    return anthropic.Anthropic(api_key=api_key)


def call_claude(system_prompt: str, user_message: str, use_cache: bool = True) -> str:
    """Call Claude with optional prompt caching for the system prompt."""
    client = get_client()

    system_blocks = [
        {
            "type": "text",
            "text": system_prompt,
            **({"cache_control": {"type": "ephemeral"}} if use_cache else {}),
        }
    ]

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_blocks,
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text


def call_claude_json(system_prompt: str, user_message: str) -> str:
    """Call Claude expecting JSON output."""
    client = get_client()

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text
