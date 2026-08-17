from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from textwrap import dedent

import streamlit as st

from core.auth_v8 import (
    ALLOWED_PROFILES,
    DEFAULT_DEVICE_TTL_DAYS,
    credential_version,
    issue_device_token,
    verify_password,
)

LOGGER = logging.getLogger("rog.v9.auth")
TRUST_COOKIE_NAME = "rog_ai_device"
COOKIE_SETTLE_SECONDS = 0.8


def _secret(name: str) -> str:
    try:
        return str(st.secrets[name])
    except Exception:
        return ""


def _cookie_secret() -> str:
    value = _secret("DEVICE_COOKIE_SECRET")
    return value if len(value) >= 32 else ""


def _credential_tag(profile: str) -> str:
    return credential_version(_cookie_secret(), _secret(f"{profile.upper()}_PASSWORD"))


def _persist_trusted_device(manager, profile: str) -> bool:
    """Queue the signed device cookie and give the browser time to commit it.

    extra-streamlit-components writes cookies in the browser. An immediate
    st.rerun can tear down the component before the write is committed, which
    made a successful login disappear on F5. This helper deliberately lets the
    component delta reach the browser before rerunning the app.
    """
    secret = _cookie_secret()
    tag = _credential_tag(profile)
    if manager is None or not secret or not tag:
        return False
    try:
        token = issue_device_token(
            profile,
            secret,
            ttl_days=DEFAULT_DEVICE_TTL_DAYS,
            credential_tag=tag,
        )
        manager.set(
            TRUST_COOKIE_NAME,
            token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=DEFAULT_DEVICE_TTL_DAYS),
            path="/",
            secure=True,
            same_site="strict",
            key=f"rog_v9_cookie_set_{profile.lower()}",
        )
        # Streamlit component writes are client-side. Do not immediately tear
        # down the component with st.rerun().
        time.sleep(COOKIE_SETTLE_SECONDS)
        return True
    except Exception as exc:
        LOGGER.warning("trusted-device cookie write failed: %s", type(exc).__name__)
        return False


def render_login_v9(manager) -> None:
    st.markdown(
        dedent(
            '''\
            <style>
            [data-testid="stSidebar"]{display:none!important}
            .block-container{max-width:440px!important;padding-top:10vh!important}
            .v9-login{text-align:center;margin-bottom:24px}
            .v9-login-logo{width:58px;height:58px;border-radius:18px;display:grid;place-items:center;margin:0 auto 16px;background:linear-gradient(135deg,#684bf0,#9b82ff);font-size:22px;font-weight:900}
            .v9-login h1{font-size:28px;margin:0}
            .v9-login p{color:#8993a4;font-size:12px}
            </style>
            <div class="v9-login"><div class="v9-login-logo">R</div><h1>ROG AI</h1><p>Family Intelligence · workspace privado</p></div>
            '''
        ).strip(),
        unsafe_allow_html=True,
    )

    with st.form("v9_login"):
        profile = st.selectbox("Perfil", ALLOWED_PROFILES)
        password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
        submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)

    if submitted:
        if not verify_password(profile, password, st.secrets):
            st.error("Perfil ou senha inválidos.")
            return

        # Establish server-side state first. The signed cookie contains no
        # password and is bound to the current password-derived credential tag.
        st.session_state.authenticated = True
        st.session_state.current_profile = profile
        st.session_state.current_agent = "orchestrator"
        st.session_state.current_view = "chat"
        st.session_state.auth_restore_attempts = 3

        persisted = _persist_trusted_device(manager, profile)
        if not persisted:
            st.warning("Login realizado, mas este navegador não pôde ser marcado como dispositivo confiável.")

        st.rerun()

    if _cookie_secret() and manager is not None:
        st.caption(f"Este navegador será reconhecido por até {DEFAULT_DEVICE_TTL_DAYS} dias após um login válido.")
    else:
        st.caption("Login persistente indisponível: verifique DEVICE_COOKIE_SECRET e o componente de cookies.")
