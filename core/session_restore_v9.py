from __future__ import annotations

import streamlit as st

from core.auth_v8 import ALLOWED_PROFILES, credential_version, verify_device_token
from core.trusted_device_v9 import read_streamlit_context_cookie
from core.supabase_auth import auth_available_for

TRUST_COOKIE_NAME = "rog_ai_device"


def _secret(name: str) -> str:
    try:
        return str(st.secrets[name])
    except Exception:
        return ""


def restore_session_from_request() -> bool:
    """Restore auth before the UI shell mounts its cookie component."""
    if bool(st.session_state.get("authenticated")):
        return True

    signing_secret = _secret("DEVICE_COOKIE_SECRET")
    if len(signing_secret) < 32:
        return False

    token = read_streamlit_context_cookie(TRUST_COOKIE_NAME)
    if not token:
        return False

    preliminary = verify_device_token(token, signing_secret)
    if not preliminary or preliminary.profile not in ALLOWED_PROFILES:
        return False
    if auth_available_for(preliminary.profile):
        return False

    password = _secret(f"{preliminary.profile.upper()}_PASSWORD")
    tag = credential_version(signing_secret, password)
    identity = verify_device_token(
        token,
        signing_secret,
        expected_credential_tag=tag,
    )
    if not identity:
        return False

    st.session_state.authenticated = True
    st.session_state.current_profile = identity.profile
    st.session_state.current_agent = "orchestrator"
    st.session_state.current_view = "chat"
    st.session_state.auth_restore_attempts = 3
    st.session_state.auth_backend = "legacy"
    st.session_state.auth_user_id = ""
    st.session_state.is_admin = identity.profile.casefold() == "allan"
    return True
