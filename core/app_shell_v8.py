from __future__ import annotations

import streamlit as st

from core.agent_runtime import AGENTS as RUNTIME_AGENTS, execute_agent
from core.auth_v8 import ALLOWED_PROFILES, verify_password
from core.ui_v8 import AGENT_META, inject_design_system, render_agent_header, render_brand, render_profile, render_welcome


def init_state() -> None:
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("current_profile", None)
    st.session_state.setdefault("current_agent", "orchestrator")
    st.session_state.setdefault("conversations_by_profile", {})
    st.session_state.setdefault("busy", False)


def clear_private_state() -> None:
    for key in ("authenticated", "current_profile", "current_agent", "conversations", "conversations_by_profile", "memory_by_profile", "long_memory", "busy", "processed_events"):
        st.session_state.pop(key, None)
    st.session_state.authenticated = False
    st.session_state.current_profile = None


def render_login() -> None:
    st.markdown('''<style>[data-testid="stSidebar"]{display:none!important}.block-container{max-width:440px!important;padding-top:10vh!important}.v8-login{text-align:center;margin-bottom:24px}.v8-login-logo{width:58px;height:58px;border-radius:18px;display:grid;place-items:center;margin:0 auto 16px;background:linear-gradient(135deg,#684bf0,#9b82ff);font-size:22px;font-weight:900}.v8-login h1{font-size:28px;margin:0}.v8-login p{color:#8993a4;font-size:12px}</style><div class="v8-login"><div class="v8-login-logo">R</div><h1>ROG AI</h1><p>Family Intelligence · workspace privado</p></div>''', unsafe_allow_html=True)
    with st.form("v8_login"):
        profile = st.selectbox("Perfil", ALLOWED_PROFILES)
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
    if submitted:
        if verify_password(profile, password, st.secrets):
            st.session_state.authenticated = True
            st.session_state.current_profile = profile
            st.session_state.current_agent = "orchestrator"
            st.rerun()
        st.error("Perfil ou senha inválidos.")


def profile_conversations(profile: str) -> dict[str, list]:
    key = profile.strip().lower()
    store = st.session_state.conversations_by_profile
    if key not in store:
        store[key] = {agent_id: [] for agent_id in RUNTIME_AGENTS}
    return store[key]


def render_sidebar(profile: str, agent_id: str) -> None:
    with st.sidebar:
        render_brand(); render_profile(profile)
        st.markdown('<div class="rog-section">Assistentes</div>', unsafe_allow_html=True)
        for aid, meta in AGENT_META.items():
            if st.button(f"{meta[0]}  {meta[1]}", key=f"v8_nav_{aid}", type="primary" if aid == agent_id else "secondary", use_container_width=True):
                st.session_state.current_agent = aid; st.rerun()
        st.divider()
        if st.button("Sair", key="v8_logout", use_container_width=True):
            clear_private_state(); st.rerun()


def process_message(profile: str, agent_id: str, history: list, text: str) -> None:
    clean = (text or "").strip()
    if not clean: return
    history.append({"role": "user", "content": clean})
    st.session_state.busy = True
    try:
        result = execute_agent(agent_id=agent_id, history=history[:-1], user_query=clean, profile=profile)
        history.append({"role": "assistant", "content": result.get("answer") or "Não recebi uma resposta válida do modelo.", "runtime": result})
    except Exception as exc:
        history.append({"role": "assistant", "content": f"Falha temporária no pipeline: `{type(exc).__name__}`. Tente novamente.", "runtime": {"agent_name": "ROG AI", "model": "fallback"}})
    finally:
        st.session_state.busy = False
    st.rerun()


def run() -> None:
    init_state(); inject_design_system()
    if not st.session_state.authenticated or st.session_state.current_profile not in ALLOWED_PROFILES:
        clear_private_state(); render_login(); st.stop()
    profile = st.session_state.current_profile
    agent_id = st.session_state.current_agent if st.session_state.current_agent in RUNTIME_AGENTS else "orchestrator"
    conversations = profile_conversations(profile); history = conversations[agent_id]
    render_sidebar(profile, agent_id); render_agent_header(agent_id)
    if not history: render_welcome(agent_id, profile)
    for message in history:
        role = message.get("role")
        with st.chat_message("user" if role == "user" else "assistant"):
            if role == "assistant":
                runtime = message.get("runtime") or {}; label = runtime.get("agent_name", "ROG AI"); model = runtime.get("model", "")
                if model: st.caption(f"{label} · {model}")
            st.markdown(message.get("content", ""))
    prompt = st.chat_input("Mensagem para o ROG AI…", disabled=bool(st.session_state.busy))
    if prompt is not None: process_message(profile, agent_id, history, prompt)
