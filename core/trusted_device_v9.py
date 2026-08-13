from __future__ import annotations

from typing import Mapping


def read_cookie(cookies: Mapping[str, object] | None, cookie_name: str) -> str:
    """Pure helper used by tests and Streamlit request-context restore."""
    if not cookies or not cookie_name:
        return ""
    try:
        return str(cookies.get(cookie_name, "") or "")
    except Exception:
        return ""


def read_streamlit_context_cookie(cookie_name: str) -> str:
    """Read a cookie delivered with the initial Streamlit request.

    Streamlit's request context is read-only. Writes/deletes remain delegated to
    the cookie component, while restore no longer waits for component hydration.
    """
    try:
        import streamlit as st
        return read_cookie(st.context.cookies, cookie_name)
    except Exception:
        return ""


def resolve_trusted_token(cookie_name: str, manager=None) -> str:
    token = read_streamlit_context_cookie(cookie_name)
    if token:
        return token
    if manager is None:
        return ""
    try:
        return str(manager.get(cookie_name) or "")
    except Exception:
        return ""
