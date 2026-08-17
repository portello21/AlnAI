from __future__ import annotations

import logging
import importlib.util
import hashlib
import html
from datetime import datetime, timedelta, timezone

import streamlit as st

try:
    import extra_streamlit_components as stx
except Exception:  # pragma: no cover
    stx = None

from core.agent_runtime import AGENTS as RUNTIME_AGENTS, execute_agent
from core.attachments import extract_document_text
from core.auth_v8 import (
    ALLOWED_PROFILES,
    DEFAULT_DEVICE_TTL_DAYS,
    credential_version,
    issue_device_token,
    verify_device_token,
    verify_password,
)
from core.database import PersistenceManager
from core.memory_service_v8 import FamilyMemoryService
from core.profile_access import allowed_namespaces, write_namespace
from core.response_jobs import cancel_response_job, consume_response_job, drain_response_tokens, response_job_status, start_response_job
from core.supabase_auth import auth_available_for
from core.ui_v8 import AGENT_META, MARK_SVG, inject_design_system, render_agent_header, render_brand, render_profile, render_welcome
from core.workspace_v8 import render_admin_view, render_creative_view, render_documents_view, render_memory_view, render_system_view

LOGGER = logging.getLogger("rog.v8")
TRUST_COOKIE_NAME = "rog_ai_device"
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_DIRECT_CONTEXT_CHARS = 12_000
MAX_AUTH_RESTORE_ATTEMPTS = 3
VALID_VIEWS = {"chat", "memories", "documents", "creative", "system", "admin"}
QUICK_ACTIONS = {
    "orchestrator": ("Organizar meu dia", "Resumir prioridades", "Planejar um projeto"),
    "personal": ("Montar minha rotina", "Comparar uma decisão", "Criar uma checklist"),
    "finance": ("Criar um orçamento", "Analisar um gasto", "Planejar uma meta"),
    "tech": ("Revisar um código", "Diagnosticar um erro", "Planejar uma arquitetura"),
    "coach": ("Criar um treino", "Rever meus hábitos", "Definir uma meta"),
    "business": ("Validar uma ideia", "Montar um plano", "Analisar uma estratégia"),
    "english": ("Practice conversation", "Review my writing", "Build a study plan"),
    "document": ("Resumir um documento", "Extrair pontos-chave", "Comparar arquivos"),
}


@st.cache_resource
def _persistence() -> PersistenceManager:
    return PersistenceManager()


@st.cache_resource
def _family_memory() -> FamilyMemoryService:
    return FamilyMemoryService()


@st.cache_data(ttl=60)
def _remote_operations_summary() -> dict:
    from core.operations_store import operations_summary
    return operations_summary(days=7)


def _cookie_secret() -> str:
    try:
        value = str(st.secrets["DEVICE_COOKIE_SECRET"])
    except Exception:
        return ""
    return value if len(value) >= 32 else ""


def _profile_password(profile: str) -> str:
    try:
        return str(st.secrets[f"{profile.upper()}_PASSWORD"])
    except Exception:
        return ""


def _credential_tag(profile: str) -> str:
    return credential_version(_cookie_secret(), _profile_password(profile))


def _cookie_manager():
    if stx is None:
        return None
    try:
        return stx.CookieManager(key="rog_v8_cookie_manager")
    except Exception:
        return None


def init_state() -> None:
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("current_profile", None)
    st.session_state.setdefault("current_agent", "orchestrator")
    st.session_state.setdefault("current_view", "chat")
    st.session_state.setdefault("conversations_by_profile", {})
    st.session_state.setdefault("busy", False)
    st.session_state.setdefault("active_response_job", None)
    st.session_state.setdefault("streamed_response", "")
    st.session_state.setdefault("auth_backend", "")
    st.session_state.setdefault("auth_user_id", "")
    st.session_state.setdefault("auth_access_token", "")
    st.session_state.setdefault("auth_refresh_token", "")
    st.session_state.setdefault("is_admin", False)
    st.session_state.setdefault("password_change_required", False)
    st.session_state.setdefault("auth_policy_checked", False)
    st.session_state.setdefault("generated_temporary_password", None)
    st.session_state.setdefault("auth_restore_attempts", 0)
    st.session_state.setdefault("shared_finance_upload", False)
    st.session_state.setdefault("auth_cookie_refresh_required", False)


def clear_private_state(*, preserve_restore_attempts: bool = True) -> None:
    attempts = int(st.session_state.get("auth_restore_attempts", 0)) if preserve_restore_attempts else 0
    active_job = st.session_state.get("active_response_job")
    if isinstance(active_job, dict):
        cancel_response_job(job_id=active_job.get("id", ""), profile=active_job.get("profile", ""), agent_id=active_job.get("agent_id", ""))
    for key in ("authenticated", "current_profile", "current_agent", "current_view", "conversations", "conversations_by_profile", "memory_by_profile", "long_memory", "busy", "active_response_job", "streamed_response", "auth_backend", "auth_user_id", "auth_access_token", "auth_refresh_token", "is_admin", "password_change_required", "auth_policy_checked", "generated_temporary_password", "processed_events", "shared_finance_upload"):
        st.session_state.pop(key, None)
    st.session_state.authenticated = False
    st.session_state.current_profile = None
    st.session_state.current_agent = "orchestrator"
    st.session_state.current_view = "chat"
    st.session_state.busy = False
    st.session_state.auth_restore_attempts = attempts


def _restore_trusted_device(manager) -> None:
    if st.session_state.authenticated:
        return
    attempts = int(st.session_state.get("auth_restore_attempts", 0))
    if attempts >= MAX_AUTH_RESTORE_ATTEMPTS:
        return
    st.session_state.auth_restore_attempts = attempts + 1
    secret = _cookie_secret()
    if not manager or not secret:
        return
    try:
        token = manager.get(TRUST_COOKIE_NAME)
    except Exception:
        token = None
    if not token:
        return
    # The token tells us a claimed profile only after its HMAC is valid. We
    # first verify signature/time, then require the current password-derived tag.
    preliminary = verify_device_token(token, secret)
    if not preliminary:
        return
    if auth_available_for(preliminary.profile):
        return
    tag = _credential_tag(preliminary.profile)
    identity = verify_device_token(token, secret, expected_credential_tag=tag)
    if identity and identity.profile in ALLOWED_PROFILES:
        st.session_state.authenticated = True
        st.session_state.current_profile = identity.profile
        st.session_state.current_agent = "orchestrator"
        st.session_state.current_view = "chat"
        st.session_state.auth_restore_attempts = MAX_AUTH_RESTORE_ATTEMPTS
        st.session_state.auth_backend = "legacy"
        st.session_state.auth_user_id = ""
        st.session_state.is_admin = identity.profile.casefold() == "allan"


def _trust_current_device(manager, profile: str) -> None:
    secret = _cookie_secret()
    tag = _credential_tag(profile)
    if not manager or not secret or not tag:
        return
    try:
        token = issue_device_token(profile, secret, ttl_days=DEFAULT_DEVICE_TTL_DAYS, credential_tag=tag)
        manager.set(TRUST_COOKIE_NAME, token, expires_at=datetime.now(timezone.utc) + timedelta(days=DEFAULT_DEVICE_TTL_DAYS), key="rog_v8_cookie_set")
    except Exception as exc:
        LOGGER.warning("trusted-device cookie write failed: %s", type(exc).__name__)


def _forget_device(manager) -> None:
    if manager:
        try:
            manager.delete(TRUST_COOKIE_NAME, key="rog_v8_cookie_delete")
        except Exception as exc:
            LOGGER.warning("trusted-device cookie delete failed: %s", type(exc).__name__)
    clear_private_state(preserve_restore_attempts=False)
    st.session_state.auth_restore_attempts = MAX_AUTH_RESTORE_ATTEMPTS


def render_login(manager) -> None:
    st.markdown('''<style>[data-testid="stSidebar"]{display:none!important}.block-container{max-width:440px!important;padding-top:10vh!important}.v8-login{text-align:center;margin-bottom:24px}.v8-login-logo{width:58px;height:58px;border-radius:18px;display:grid;place-items:center;margin:0 auto 16px;background:linear-gradient(135deg,#684bf0,#9b82ff);font-size:22px;font-weight:900}.v8-login h1{font-size:28px;margin:0}.v8-login p{color:#8993a4;font-size:12px}</style><div class="v8-login"><div class="v8-login-logo">R</div><h1>ROG AI</h1><p>Family Intelligence · workspace privado</p></div>''', unsafe_allow_html=True)
    with st.form("v8_login"):
        profile = st.selectbox("Perfil", ALLOWED_PROFILES)
        password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
        submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
    if submitted:
        if verify_password(profile, password, st.secrets):
            st.session_state.authenticated = True
            st.session_state.current_profile = profile
            st.session_state.current_agent = "orchestrator"
            st.session_state.current_view = "chat"
            st.session_state.auth_restore_attempts = MAX_AUTH_RESTORE_ATTEMPTS
            _trust_current_device(manager, profile)
            st.rerun()
        st.error("Perfil ou senha inválidos.")
    if _cookie_secret() and manager:
        st.caption(f"Este navegador será reconhecido por até {DEFAULT_DEVICE_TTL_DAYS} dias após um login válido.")
    else:
        st.caption("Login persistente indisponível até DEVICE_COOKIE_SECRET e o componente de cookies estarem configurados.")


def _safe_history(value) -> dict[str, list]:
    output = {agent_id: [] for agent_id in RUNTIME_AGENTS}
    if not isinstance(value, dict):
        return output
    for agent_id in output:
        items = value.get(agent_id, [])
        if isinstance(items, list):
            output[agent_id] = [item for item in items[-120:] if isinstance(item, dict)]
    return output


def profile_conversations(profile: str) -> dict[str, list]:
    key = profile.strip().lower()
    store = st.session_state.conversations_by_profile
    if key not in store:
        try:
            persisted = _persistence().load_data().get(key, {})
            store[key] = _safe_history(persisted.get("history", {}))
        except Exception as exc:
            LOGGER.warning("history load failed: %s", type(exc).__name__)
            store[key] = _safe_history({})
    return store[key]


def persist_conversations(profile: str, conversations: dict[str, list]) -> None:
    key = profile.strip().lower()
    try:
        existing = _persistence().load_data().get(key, {})
        _persistence().save({key: {"user_facts": existing.get("user_facts", []) if isinstance(existing, dict) else [], "history": _safe_history(conversations)}})
    except Exception as exc:
        LOGGER.warning("history persistence failed: %s", type(exc).__name__)


def _goto(view: str) -> None:
    if view in VALID_VIEWS:
        st.session_state.current_view = view


def _conversation_markdown(messages: list[dict]) -> str:
    lines = ["# Conversa ROG AI", ""]
    for item in messages:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        label = "Você" if item["role"] == "user" else "ROG AI"
        lines.extend((f"## {label}", "", str(item.get("content") or "").strip(), ""))
    return "\n".join(lines).strip() + "\n"


def _render_conversation_history(profile: str, agent_id: str, conversations: dict[str, list]) -> None:
    persistence = _persistence()
    current = conversations.get(agent_id, [])
    with st.expander("Histórico de conversas", expanded=False):
        search = st.text_input("Buscar", key=f"v8_history_search_{agent_id}", placeholder="Título da conversa")
        archives = persistence.list_conversation_archives(profile=profile, agent_id=agent_id, search=search)
        if not archives:
            st.caption("Nenhuma conversa arquivada para este agente.")
        for archive in archives[:12]:
            title = str(archive.get("title") or "Conversa")
            left, right = st.columns([5, 1])
            with left:
                if st.button(title, key=f"v8_restore_{archive['id']}", use_container_width=True, help="Restaurar esta conversa"):
                    restored = persistence.load_conversation_archive(profile=profile, agent_id=agent_id, archive_id=archive["id"])
                    if restored:
                        if current:
                            persistence.archive_conversation(profile=profile, agent_id=agent_id, messages=current)
                        conversations[agent_id] = restored
                        persist_conversations(profile, conversations)
                        _goto("chat")
                        st.rerun()
            with right:
                with st.popover("⋯"):
                    st.caption("Excluir somente deste perfil e agente.")
                    if st.button("Excluir", key=f"v8_delete_archive_{archive['id']}", type="primary", use_container_width=True):
                        if persistence.delete_conversation_archive(profile=profile, agent_id=agent_id, archive_id=archive["id"]):
                            st.rerun()
        if current:
            st.download_button(
                "Exportar conversa atual",
                data=_conversation_markdown(current),
                file_name=f"rog-ai-{profile.lower()}-{agent_id}.md",
                mime="text/markdown",
                key=f"v8_export_{agent_id}",
                use_container_width=True,
            )


def render_sidebar(profile: str, agent_id: str, conversations: dict[str, list], manager) -> None:
    with st.sidebar:
        render_brand(); render_profile(profile)
        st.markdown('<div class="rog-section">Assistentes</div>', unsafe_allow_html=True)
        for aid, meta in AGENT_META.items():
            if st.button(meta[1], key=f"v8_nav_{aid}", type="primary" if aid == agent_id and st.session_state.current_view == "chat" else "secondary", use_container_width=True, disabled=bool(st.session_state.busy)):
                st.session_state.current_agent = aid; _goto("chat"); st.rerun()
        st.markdown('<div class="rog-section">Workspace</div>', unsafe_allow_html=True)
        for view, label in (("chat", "Conversa"), ("memories", "Memórias"), ("documents", "Documentos"), ("creative", "Estúdio Criativo"), ("system", "Sistema")):
            if st.button(label, key=f"v8_view_{view}", type="primary" if st.session_state.current_view == view else "secondary", use_container_width=True):
                _goto(view); st.rerun()
        if st.session_state.get("is_admin") and st.button("Administração", key="v8_view_admin", type="primary" if st.session_state.current_view == "admin" else "secondary", use_container_width=True):
            _goto("admin"); st.rerun()
        if st.button("Nova conversa", key="v8_new_chat", use_container_width=True, icon=":material/edit_square:"):
            if conversations.get(agent_id):
                _persistence().archive_conversation(profile=profile, agent_id=agent_id, messages=conversations[agent_id])
            conversations[agent_id] = []; persist_conversations(profile, conversations); _goto("chat"); st.rerun()
        _render_conversation_history(profile, agent_id, conversations)
        if agent_id == "finance" and profile.lower() in {"allan", "beatriz"}:
            st.toggle("Financeiro compartilhado", key="shared_finance_upload", help="Quando ativo, documentos e comandos explícitos de memória usam apenas o espaço financeiro compartilhado Allan ↔ Beatriz.")
        else:
            st.session_state.shared_finance_upload = False
        st.divider()
        if st.button("Trocar perfil", key="v8_switch_profile", use_container_width=True): _forget_device(manager); st.rerun()
        if st.button("Sair", key="v8_logout", use_container_width=True): _forget_device(manager); st.rerun()


def render_navigation_bar(profile: str, agent_id: str, conversations: dict[str, list], manager) -> None:
    """Permanent navigation that remains usable even when Streamlit's sidebar is hidden."""
    _, agent_name, _ = AGENT_META.get(agent_id, AGENT_META["orchestrator"])
    with st.container(key="rog_top_nav"):
        brand, context, menu = st.columns([1.15, 1.7, .65], vertical_alignment="center")
        with brand:
            st.markdown(f'<div class="rog-top-brand"><div class="rog-logo">{MARK_SVG}</div><div><strong>ROG AI</strong><span>FAMILY INTELLIGENCE</span></div></div>', unsafe_allow_html=True)
        with context:
            status = "Processando" if st.session_state.busy else "Disponível"
            state_class = " is-busy" if st.session_state.busy else ""
            st.markdown(f'<div class="rog-top-context"><strong>{html.escape(agent_name)}</strong><span class="rog-inline-status{state_class}"><i></i>{status}</span><span class="rog-profile-context">{html.escape(profile.title())} · privado</span></div>', unsafe_allow_html=True)
        with menu:
            label = "Fechar" if st.session_state.get("v8_top_menu_open") else "Menu"
            icon = ":material/close:" if st.session_state.get("v8_top_menu_open") else ":material/menu:"
            if st.button(label, key="v8_top_menu_button", icon=icon, use_container_width=True):
                st.session_state.v8_top_menu_open = not bool(st.session_state.get("v8_top_menu_open"))
    if not st.session_state.get("v8_top_menu_open"):
        return
    with st.container(key="rog_top_menu_panel"):
        heading, close = st.columns([4, 1], vertical_alignment="center")
        with heading:
            st.markdown("**Navegação**")
        with close:
            if st.button("Fechar", key="v8_top_menu_close", icon=":material/close:", use_container_width=True):
                st.session_state.v8_top_menu_open = False
                st.rerun()
        agent_ids = list(AGENT_META)
        selected_agent = st.selectbox("Assistente", agent_ids, index=agent_ids.index(agent_id), format_func=lambda aid: AGENT_META[aid][1], key="v8_top_agent")
        if st.button("Abrir assistente", key="v8_top_open_agent", type="primary", use_container_width=True, disabled=bool(st.session_state.busy), icon=":material/smart_toy:"):
            st.session_state.current_agent = selected_agent
            st.session_state.v8_top_menu_open = False
            _goto("chat")
            st.rerun()
        view_columns = st.columns(2)
        for index, (target, label) in enumerate((("chat", "Conversa"), ("memories", "Memórias"), ("documents", "Documentos"), ("creative", "Estúdio"), ("system", "Sistema"))):
            with view_columns[index % 2]:
                if st.button(label, key=f"v8_top_view_{target}", type="primary" if st.session_state.current_view == target else "secondary", use_container_width=True):
                    st.session_state.v8_top_menu_open = False
                    _goto(target)
                    st.rerun()
        if st.session_state.get("is_admin") and st.button("Administração", key="v8_top_admin", use_container_width=True, icon=":material/admin_panel_settings:"):
            st.session_state.v8_top_menu_open = False
            _goto("admin")
            st.rerun()
        st.divider()
        if st.button("Nova conversa", key="v8_top_new_chat", use_container_width=True, icon=":material/edit_square:"):
            if conversations.get(agent_id):
                _persistence().archive_conversation(profile=profile, agent_id=agent_id, messages=conversations[agent_id])
            conversations[agent_id] = []
            persist_conversations(profile, conversations)
            st.session_state.v8_top_menu_open = False
            _goto("chat")
            st.rerun()
        account_a, account_b = st.columns(2)
        with account_a:
            if st.button("Trocar perfil", key="v8_top_switch", use_container_width=True):
                _forget_device(manager)
                st.rerun()
        with account_b:
            if st.button("Sair", key="v8_top_logout", use_container_width=True):
                _forget_device(manager)
                st.rerun()


def _process_files(profile: str, agent_id: str, files: list) -> tuple[list[str], list[str]]:
    from core.vector_rag import add_document_to_rag
    notes, direct_context = [], []
    namespace = write_namespace(profile, agent_id, shared_finance=bool(st.session_state.shared_finance_upload))
    for uploaded in files[:10]:
        try:
            raw = uploaded.getvalue(); name = getattr(uploaded, "name", "arquivo"); mime = getattr(uploaded, "type", "") or ""
            if len(raw) > MAX_FILE_BYTES:
                notes.append(f"📎 {name}: excede o limite de 20 MB."); continue
            extraction = extract_document_text(raw, name, mime)
            if not extraction.get("success"):
                notes.append(f"📎 {name}: não foi possível extrair conteúdo."); continue
            text = str(extraction.get("text", "")).strip()
            result = add_document_to_rag(extraction["file_hash"], text, {"profile": profile.strip().lower(), "agent_id": agent_id, "namespace": namespace, "filename": extraction["filename"], "mime_type": mime or "unknown", "extraction_method": extraction.get("method") or "unknown"})
            if result.get("success"):
                notes.append(f"📎 {extraction['filename']} · {result.get('chunks', 0)} partes indexadas"); direct_context.append(f"ARQUIVO {extraction['filename']}:\n{text}")
            else: notes.append(f"📎 {name}: falha ao indexar.")
        except Exception as exc:
            LOGGER.warning("attachment processing failed: %s", type(exc).__name__); notes.append("📎 Um anexo não pôde ser processado.")
    joined = "\n\n".join(direct_context)
    if len(joined) > MAX_DIRECT_CONTEXT_CHARS: joined = joined[:MAX_DIRECT_CONTEXT_CHARS]
    return notes, [joined] if joined else []


def _submission_parts(submission) -> tuple[str, list, object | None]:
    if isinstance(submission, str): return submission, [], None
    try: text = str(submission.text or "")
    except Exception: text = str(submission.get("text", "") if submission else "")
    try: files = list(submission.files or [])
    except Exception: files = list(submission.get("files", []) if submission else [])
    try: audio = submission.audio
    except Exception: audio = submission.get("audio") if submission else None
    return text, files, audio


def process_submission(profile: str, agent_id: str, conversations: dict[str, list], submission) -> None:
    if st.session_state.busy: return
    history = conversations[agent_id]; text, files, audio = _submission_parts(submission)
    display_parts, query_parts, extra_context_parts = [], [], []
    clean = text.strip()
    if clean: display_parts.append(clean); query_parts.append(clean)
    if clean and not files and audio is None:
        memory_result = _family_memory().process_explicit_command(profile, agent_id, clean, shared_finance=bool(st.session_state.shared_finance_upload))
        if memory_result.handled:
            history.append({"role":"user","content":clean}); history.append({"role":"assistant","content":memory_result.message,"runtime":{"agent_name":"Memory Engine","model":"memory-v8","success":memory_result.success}}); persist_conversations(profile, conversations); st.rerun()
    if files:
        file_notes, file_context = _process_files(profile, agent_id, files); display_parts.extend(file_notes); extra_context_parts.extend(file_context)
        if not clean: query_parts.append("Analise os arquivos anexados e destaque os pontos mais importantes.")
    if audio is not None:
        try:
            from providers.audio import transcribe_audio_bytes
            transcript = transcribe_audio_bytes(audio.getvalue()).strip()
            if transcript: display_parts.append(f"🎙️ {transcript}"); query_parts.append(transcript)
            else: display_parts.append("🎙️ O áudio não pôde ser transcrito.")
        except Exception as exc:
            LOGGER.warning("audio transcription failed: %s", type(exc).__name__); display_parts.append("🎙️ O áudio não pôde ser transcrito.")
    query = "\n\n".join(part for part in query_parts if part).strip()
    if not query: return
    try:
        from core.vector_rag import query_rag
        rag_docs = query_rag(query, n_results=3, profile=profile, agent_id=agent_id, namespaces=allowed_namespaces(profile, agent_id))
        if rag_docs: extra_context_parts.append("CONTEXTO DE DOCUMENTOS RELEVANTES:\n" + "\n\n".join(rag_docs))
    except Exception as exc: LOGGER.warning("secure RAG query failed: %s", type(exc).__name__)
    shared_memory_context = _family_memory().shared_finance_context(profile, agent_id, query)
    if shared_memory_context: extra_context_parts.append(shared_memory_context)
    user_display = "\n\n".join(display_parts) or query; history.append({"role":"user","content":user_display}); st.session_state.busy = True
    try:
        job_id = start_response_job(
            profile=profile,
            agent_id=agent_id,
            target=execute_agent,
            kwargs={"agent_id": agent_id, "history": history[:-1], "user_query": query, "extra_context": "\n\n".join(extra_context_parts) or None, "profile": profile},
            streaming=True,
        )
        st.session_state.active_response_job = {"id": job_id, "profile": profile, "agent_id": agent_id}
        st.session_state.streamed_response = ""
    except Exception as exc:
        LOGGER.exception("agent job start failed: %s", type(exc).__name__)
        history.append({"role":"assistant","content":"O serviço de IA encontrou uma falha temporária. Sua mensagem foi preservada; tente novamente em instantes.","runtime":{"agent_name":"ROG AI","model":"fallback","success":False}})
        st.session_state.busy = False
    persist_conversations(profile, conversations)
    st.rerun()


@st.fragment(run_every=0.5)
def _render_active_response(profile: str, agent_id: str, conversations: dict[str, list]) -> None:
    active = st.session_state.get("active_response_job")
    if not isinstance(active, dict) or active.get("profile") != profile or active.get("agent_id") != agent_id:
        return
    status = response_job_status(job_id=active.get("id", ""), profile=profile, agent_id=agent_id)
    token_batch = drain_response_tokens(job_id=active.get("id", ""), profile=profile, agent_id=agent_id)
    if token_batch:
        st.session_state.streamed_response = str(st.session_state.get("streamed_response", "")) + token_batch
    if st.session_state.get("streamed_response"):
        with st.chat_message("assistant", avatar=":material/auto_awesome:"):
            st.markdown(st.session_state.streamed_response + ("▌" if status["state"] == "running" else ""))
    if status["state"] == "running":
        st.caption("ROG AI está preparando a resposta…")
        if st.button("Cancelar geração", key=f"v8_cancel_{active.get('id')}", use_container_width=True):
            cancel_response_job(job_id=active.get("id", ""), profile=profile, agent_id=agent_id)
            consume_response_job(job_id=active.get("id", ""), profile=profile, agent_id=agent_id)
            st.session_state.active_response_job = None
            st.session_state.streamed_response = ""
            st.session_state.busy = False
            st.rerun()
        return
    final = consume_response_job(job_id=active.get("id", ""), profile=profile, agent_id=agent_id)
    if final["state"] == "done" and isinstance(final.get("result"), dict):
        result = final["result"]
        answer = str(result.get("answer") or "").strip() or "Não recebi uma resposta válida do modelo. Tente novamente."
        conversations[agent_id].append({"role": "assistant", "content": answer, "runtime": result})
    elif final["state"] != "cancelled":
        conversations[agent_id].append({"role":"assistant","content":"O serviço de IA encontrou uma falha temporária. Sua mensagem foi preservada; tente novamente em instantes.","runtime":{"agent_name":"ROG AI","model":"fallback","success":False}})
    st.session_state.active_response_job = None
    st.session_state.streamed_response = ""
    st.session_state.busy = False
    persist_conversations(profile, conversations)
    st.rerun()


def _render_chat(profile: str, agent_id: str, conversations: dict[str, list]) -> None:
    history = conversations[agent_id]
    if not history:
        render_welcome(agent_id, profile)
        st.markdown('<div class="rog-quick-label">Ações rápidas</div>', unsafe_allow_html=True)
        columns = st.columns(3)
        for column, prompt in zip(columns, QUICK_ACTIONS[agent_id]):
            with column:
                if st.button(prompt, key=f"v8_quick_{agent_id}_{prompt}", use_container_width=True, disabled=bool(st.session_state.busy)):
                    process_submission(profile, agent_id, conversations, prompt)
    for message_index, message in enumerate(history):
        role = message.get("role")
        avatar = ":material/person:" if role == "user" else ":material/auto_awesome:"
        with st.chat_message("user" if role == "user" else "assistant", avatar=avatar):
            runtime = {}
            if role == "assistant":
                runtime = message.get("runtime") or {}; label = runtime.get("agent_name", "ROG AI")
                st.caption(str(label))
            content = str(message.get("content", ""))
            st.markdown(content)
            if role == "assistant" and content:
                message_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                feedback_key = f"feedback_{profile}_{agent_id}_{message_hash[:16]}"
                if st.session_state.get(feedback_key):
                    st.caption("Obrigado pelo feedback.")
                else:
                    positive, negative, spacer = st.columns([1.2, 1.6, 7.2])
                    with positive:
                        if st.button("Útil", key=f"positive_{message_index}_{message_hash[:12]}", help="Resposta útil", icon=":material/thumb_up:"):
                            if _persistence().save_feedback(profile=profile, agent_id=agent_id, message_hash=message_hash, rating=1, provider=runtime.get("provider", ""), model=runtime.get("model", "")):
                                st.session_state[feedback_key] = True; st.rerun()
                    with negative:
                        with st.popover("Melhorar", icon=":material/thumb_down:"):
                            reason = st.selectbox("O que faltou?", ("Incorreta", "Incompleta", "Lenta", "Não usou o documento", "Agente errado"), key=f"reason_{message_index}_{message_hash[:12]}")
                            if st.button("Enviar feedback", key=f"negative_{message_index}_{message_hash[:12]}", use_container_width=True):
                                if _persistence().save_feedback(profile=profile, agent_id=agent_id, message_hash=message_hash, rating=-1, reason=reason, provider=runtime.get("provider", ""), model=runtime.get("model", "")):
                                    st.session_state[feedback_key] = True; st.rerun()
    if st.session_state.busy:
        _render_active_response(profile, agent_id, conversations)
    audio_ready = importlib.util.find_spec("whisper") is not None
    submission = st.chat_input("Mensagem para o ROG AI…", key="v8_chat_input", disabled=bool(st.session_state.busy), accept_file="multiple", file_type=["txt","md","csv","json","pdf","docx","xlsx","png","jpg","jpeg","webp"], max_upload_size=20, accept_audio=audio_ready)
    if submission is not None: process_submission(profile, agent_id, conversations, submission)


def run() -> None:
    init_state(); inject_design_system(); manager = _cookie_manager(); _restore_trusted_device(manager)
    if st.session_state.get("authenticated") and st.session_state.get("auth_cookie_refresh_required") and manager:
        from core.login_v9 import persist_supabase_session
        if persist_supabase_session(manager, str(st.session_state.get("current_profile") or ""), str(st.session_state.get("auth_refresh_token") or "")):
            st.session_state.auth_cookie_refresh_required = False
    if not st.session_state.authenticated or st.session_state.current_profile not in ALLOWED_PROFILES:
        clear_private_state(preserve_restore_attempts=True); render_login(manager); st.stop()
    profile = st.session_state.current_profile
    if not st.session_state.get("auth_policy_checked") and st.session_state.get("auth_access_token"):
        from core.supabase_auth import validate_access_token
        checked = validate_access_token(str(st.session_state.auth_access_token))
        if checked and checked.user_id == str(st.session_state.get("auth_user_id") or ""):
            st.session_state.password_change_required = checked.password_change_required
            st.session_state.is_admin = checked.is_admin
        st.session_state.auth_policy_checked = True
    if st.session_state.get("password_change_required"):
        from core.supabase_auth import AuthIdentity, complete_required_password_change
        st.title("Crie sua nova senha")
        st.caption("Esta senha substituirá a temporária. Use pelo menos 12 caracteres.")
        with st.form("required_password_change"):
            password = st.text_input("Nova senha", type="password")
            confirmation = st.text_input("Confirme a nova senha", type="password")
            submitted = st.form_submit_button("Salvar nova senha", type="primary", use_container_width=True)
        if submitted:
            if len(password) < 12:
                st.error("Use pelo menos 12 caracteres.")
            elif password != confirmation:
                st.error("As duas senhas não são iguais.")
            else:
                identity = AuthIdentity(
                    user_id=str(st.session_state.get("auth_user_id") or ""),
                    profile=profile,
                    access_token=str(st.session_state.get("auth_access_token") or ""),
                    refresh_token=str(st.session_state.get("auth_refresh_token") or ""),
                    is_admin=bool(st.session_state.get("is_admin")),
                    password_change_required=True,
                )
                if complete_required_password_change(identity, password):
                    st.session_state.password_change_required = False
                    st.success("Senha alterada com sucesso.")
                    st.rerun()
                else:
                    st.error("Não foi possível alterar a senha. Saia, entre novamente com a senha temporária e tente outra vez.")
        st.stop()
    agent_id = st.session_state.current_agent if st.session_state.current_agent in RUNTIME_AGENTS else "orchestrator"
    view = st.session_state.current_view if st.session_state.current_view in VALID_VIEWS else "chat"
    st.session_state.current_agent = agent_id; st.session_state.current_view = view; conversations = profile_conversations(profile)
    render_sidebar(profile, agent_id, conversations, manager)
    render_navigation_bar(profile, agent_id, conversations, manager)
    shared_scope = bool(st.session_state.shared_finance_upload) and agent_id == "finance" and profile.lower() in {"allan", "beatriz"}
    if view == "memories": render_memory_view(profile, agent_id, _family_memory(), shared_finance=shared_scope); return
    if view == "documents": render_documents_view(profile, agent_id, _process_files, shared_finance=shared_scope); return
    if view == "creative": render_creative_view(profile=profile, user_id=str(st.session_state.get("auth_user_id") or "")); return
    if view == "system":
        from core.supabase_auth import AuthIdentity
        auth_identity = AuthIdentity(user_id=str(st.session_state.get("auth_user_id") or ""), profile=profile, access_token=str(st.session_state.get("auth_access_token") or ""), is_admin=bool(st.session_state.get("is_admin")))
        render_system_view(cookie_ready=bool(_cookie_secret() and manager), profile=profile, feedback=_persistence().feedback_summary(profile), is_admin=bool(st.session_state.get("is_admin")), auth_backend=str(st.session_state.get("auth_backend") or "legacy"), operations=_remote_operations_summary() if st.session_state.get("is_admin") else {}, auth_identity=auth_identity); return
    if view == "admin":
        if not st.session_state.get("is_admin"):
            _goto("chat"); st.rerun()
        render_admin_view(access_token=str(st.session_state.get("auth_access_token") or ""), current_user_id=str(st.session_state.get("auth_user_id") or ""), feedback=_persistence().feedback_summary(profile), operations=_remote_operations_summary()); return
    _render_chat(profile, agent_id, conversations)

