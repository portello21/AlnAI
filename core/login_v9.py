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
from core.config import Config
from core.supabase_auth import auth_available_for, migrate_legacy_password, sign_in_profile
from core.operations_store import record_audit_async
from core.observability import capture_product_event

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
        blocked_until = float(st.session_state.get("login_blocked_until", 0.0) or 0.0)
        if blocked_until > time.monotonic():
            st.error("Muitas tentativas. Aguarde alguns minutos antes de tentar novamente.")
            return
        supabase_configured = auth_available_for(profile)
        supabase_identity = sign_in_profile(profile, password) if supabase_configured else None
        legacy_valid = Config.LEGACY_AUTH_FALLBACK and verify_password(profile, password, st.secrets)
        migrated = False
        if not supabase_identity and supabase_configured and legacy_valid:
            migrated = migrate_legacy_password(profile, password)
            if migrated:
                supabase_identity = sign_in_profile(profile, password)
        legacy_allowed = Config.LEGACY_AUTH_FALLBACK and not supabase_configured
        if not supabase_identity and not (legacy_allowed and verify_password(profile, password, st.secrets)):
            failures = int(st.session_state.get("failed_login_attempts", 0)) + 1
            st.session_state.failed_login_attempts = failures
            if failures >= 5:
                st.session_state.login_blocked_until = time.monotonic() + 300
                st.session_state.failed_login_attempts = 0
            record_audit_async(event_type="auth.login", outcome="denied", profile=profile, metadata={"auth_backend": "supabase" if auth_available_for(profile) else "legacy"})
            st.error("Perfil ou senha inválidos.")
            return

        # Establish server-side state first. The signed cookie contains no
        # password and is bound to the current password-derived credential tag.
        st.session_state.authenticated = True
        st.session_state.current_profile = profile
        st.session_state.current_agent = "orchestrator"
        st.session_state.current_view = "chat"
        st.session_state.auth_restore_attempts = 3
        st.session_state.auth_backend = "supabase" if supabase_identity else "legacy"
        st.session_state.auth_user_id = supabase_identity.user_id if supabase_identity else ""
        st.session_state.auth_access_token = supabase_identity.access_token if supabase_identity else ""
        st.session_state.auth_refresh_token = supabase_identity.refresh_token if supabase_identity else ""
        st.session_state.is_admin = bool(supabase_identity.is_admin) if supabase_identity else profile.casefold() == "allan"
        st.session_state.password_change_required = bool(supabase_identity.password_change_required) if supabase_identity else False
        st.session_state.failed_login_attempts = 0
        st.session_state.login_blocked_until = 0.0
        record_audit_async(event_type="auth.login", outcome="success", user_id=supabase_identity.user_id if supabase_identity else "", profile=profile, metadata={"auth_backend": "supabase" if supabase_identity else "legacy"})
        if migrated:
            record_audit_async(event_type="auth.password_migrated", outcome="success", user_id=supabase_identity.user_id, profile=profile, metadata={"auth_backend": "supabase"})
        capture_product_event("login_success", user_id=supabase_identity.user_id if supabase_identity else "", properties={"auth_backend": "supabase" if supabase_identity else "legacy"})

        persisted = _persist_trusted_device(manager, profile) if not supabase_identity else False
        if not supabase_identity and not persisted:
            st.warning("Login realizado, mas este navegador não pôde ser marcado como dispositivo confiável.")

        st.rerun()

    if any(auth_available_for(item) for item in ALLOWED_PROFILES):
        st.caption("Contas migradas usam autenticação individual Supabase. Perfis ainda não migrados podem usar o acesso legado quando autorizado.")
    elif _cookie_secret() and manager is not None:
        st.caption(f"Este navegador será reconhecido por até {DEFAULT_DEVICE_TTL_DAYS} dias após um login válido.")
    else:
        st.caption("Login persistente indisponível: verifique DEVICE_COOKIE_SECRET e o componente de cookies.")

