import json
import time
import hashlib
import re
import httpx
import os
import base64
import hmac
import streamlit as st
import streamlit.components.v1 as components
from duckduckgo_search import DDGS

from core.config import Config
from core.database import PersistenceManager
from core.vector_rag import add_document_to_rag, query_rag

from core.profile_access import (
    allowed_namespaces,
    write_namespace,
)

from core.sandbox import run_code
from core.reports import generate_markdown_report, generate_csv_report
from core.attachments import calculate_file_sha256, extract_document_text
from core.skills_loader import list_available_skills, load_skill
from core.llm_router import chat as llm_chat, local_available
from core.agent_runtime import execute_agent
from core.memory_engine import MemoryEngine
from core.memory_commands import MemoryCommandProcessor
from core.memory_consolidator import MemoryConsolidator
from providers.vision import analyze_image
from providers.audio import transcribe_audio_bytes

Config.validate()
pm = PersistenceManager()

# Setup de Pagina e Tema Strict
_memory_engine_v2 = MemoryEngine()
_memory_commands = MemoryCommandProcessor(_memory_engine_v2)
_memory_consolidator = MemoryConsolidator(_memory_engine_v2)


def should_consider_auto_memory(text: str) -> bool:
    text = (text or "").strip()

    if len(text) < 12:
        return False

    lowered = text.lower()

    transient_prefixes = (
        "qual ",
        "quem ",
        "quando ",
        "onde ",
        "como ",
        "porque ",
        "por que ",
        "quanto ",
        "me diga ",
        "explique ",
        "faça ",
        "faca ",
        "crie ",
        "gere ",
        "procure ",
        "pesquise ",
    )

    if lowered.startswith(transient_prefixes):
        return False

    durable_markers = (
        "eu prefiro",
        "prefiro ",
        "eu gosto",
        "minha meta",
        "meu objetivo",
        "eu trabalho",
        "meu trabalho",
        "eu moro",
        "estou desenvolvendo",
        "meu projeto",
        "meu carro",
        "minha rotina",
        "quero aprender",
        "estou aprendendo",
        "a partir de agora",
        "daqui pra frente",
        "daqui para frente",
    )

    return any(
        marker in lowered
        for marker in durable_markers
    )

st.set_page_config(page_title="ROG AI - Unified Core", page_icon="ROG", layout="wide", initial_sidebar_state="expanded")

# --- Autenticacao Segura (Sem dicts hardcoded p/ bypass real) ---
# --- Sessao / Auto-login local ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "current_profile" not in st.session_state:
    st.session_state.current_profile = None

# Em ambiente local, entra automaticamente no perfil Allan.
# Quando publicarmos o ROG AI, este comportamento sera substituido
# por autenticacao persistente segura.
_is_local = os.environ.get("ROG_LOCAL_AUTOLOGIN", "1") == "1"

if _is_local and not st.session_state.authenticated:
    st.session_state.authenticated = True
    st.session_state.current_profile = "Allan"

def verify_auth(username, input_pass):
    try:
        secret_key = f"{username.upper()}_PASSWORD"
        real_pass = st.secrets[secret_key]
        return hmac.compare_digest(input_pass.encode('utf-8'), real_pass.encode('utf-8'))
    except KeyError:
        return False

if not st.session_state.authenticated:
    st.markdown("""<style>
        .stApp { background: #080a0c; color:#e9edef; }
        .login-box { max-width: 360px; margin: 12vh auto; padding: 40px; background: #0d1114; border: 1px solid rgba(255,255,255,0.08); border-radius: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.5); text-align: center; }
        .login-mark { width: 56px; height: 56px; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center; border-radius: 14px; background: rgba(0, 168, 132, 0.1); border: 1px solid rgba(0,168,132,0.3); color: #00a884; font-size: 24px; font-weight: 800; }
        </style>""", unsafe_allow_html=True)
    st.markdown('<div class="login-box"><div class="login-mark">R</div><h2 style="margin:0 0 5px;font-size:22px;">ROG AI</h2><p style="color:#8696a0;font-size:13px;margin-bottom:30px;">Acesso Restrito</p>', unsafe_allow_html=True)
    
    with st.form("auth_form"):
        p_choice = st.selectbox("Perfil", ["Allan", "Beatriz", "Natan", "Tainan"], label_visibility="collapsed")
        i_pass = st.text_input("Senha", type="password", placeholder="Master Password", label_visibility="collapsed")
        submitted = st.form_submit_button("Conectar", use_container_width=True)
        if submitted:
            if verify_auth(p_choice, i_pass):
                st.session_state.authenticated = True
                st.session_state.current_profile = p_choice
                st.rerun()
            else:
                st.error("Credenciais invalidas ou nao configuradas em secrets.toml.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- Arquitetura Global ---
AGENTS = {
    "orchestrator": {
        "name": "ROG AI Core",
        "icon": "[CORE]",
        "description": "Inteligencia primaria multi-ferramenta.",
        "model": "deepseek-chat",
    },
    "personal": {
        "name": "Personal Agent",
        "icon": "[PERSONAL]",
        "description": "Logistica, rotina e organizacao pessoal.",
        "model": "deepseek-chat",
    },
    "finance": {
        "name": "Finance Agent",
        "icon": "[FINANCE]",
        "description": "Planejamento e analise financeira.",
        "model": "deepseek-reasoner",
    },
    "tech": {
        "name": "Tech Agent",
        "icon": "[TECH]",
        "description": "Hardware, software e engenharia de sistemas.",
        "model": "deepseek-reasoner",
    },
    "coach": {
        "name": "Coach Agent",
        "icon": "[COACH]",
        "description": "Treinamento, fisiologia e biomecanica.",
        "model": "deepseek-chat",
    },
    "business": {
        "name": "Business Agent",
        "icon": "[BUSINESS]",
        "description": "Negocios, estrategia e geracao de receita.",
        "model": "deepseek-reasoner",
    },
    "english": {
        "name": "English Teacher",
        "icon": "[ENGLISH]",
        "description": "Ingles, traducao, conversacao e fluencia.",
        "model": "deepseek-chat",
    },
    "document": {
        "name": "Document Agent",
        "icon": "[DOC]",
        "description": "Analise local de documentos, OCR e RAG.",
        "model": "qwen3",
    },
}
if "current_agent" not in st.session_state: st.session_state.current_agent = "orchestrator"
if "memory_by_profile" not in st.session_state:
    st.session_state.memory_by_profile = {}

_profile_memory = str(
    st.session_state.current_profile
    or ""
).strip().lower()

if _profile_memory not in st.session_state.memory_by_profile:

    all_memory = (
        pm.load_data()
        if hasattr(
            pm,
            "load_data",
        )
        else {}
    )

    profile_memory = {}

    if isinstance(
        all_memory,
        dict,
    ):

        candidate = all_memory.get(
            _profile_memory,
            {},
        )

        if isinstance(
            candidate,
            dict,
        ):
            profile_memory = candidate

    st.session_state.memory_by_profile[
        _profile_memory
    ] = profile_memory

st.session_state.long_memory = (
    st.session_state.memory_by_profile[
        _profile_memory
    ]
)
if "processed_events" not in st.session_state: st.session_state.processed_events = set()
if "conversations_by_profile" not in st.session_state:
    st.session_state.conversations_by_profile = {}

_profile_chat = str(
    st.session_state.current_profile
    or ""
).strip().lower()

if _profile_chat not in st.session_state.conversations_by_profile:

    st.session_state.conversations_by_profile[
        _profile_chat
    ] = {
        key: []
        for key in AGENTS
    }

st.session_state.conversations = (
    st.session_state.conversations_by_profile[
        _profile_chat
    ]
)

current_profile = st.session_state.current_profile

profile_key = str(
    current_profile
    or ""
).strip().lower()

agent_id = st.session_state.current_agent
agent = AGENTS[agent_id]

# ============================================================
# ALLAN_AI_BETA_UI_V1
# Release candidate visual / responsive stabilization
# ============================================================

st.markdown("""
<style>

/* ---------- TOKENS ---------- */

:root {
    --allan-bg: #080a0c;
    --allan-surface: #0d1114;
    --allan-surface-2: #121619;
    --allan-border: rgba(255,255,255,.075);
    --allan-border-strong: rgba(255,255,255,.12);
    --allan-text: #edf1f3;
    --allan-muted: #8b949b;
    --allan-accent: #00a884;
}


/* ---------- STREAMLIT CHROME ---------- */

html, body,
[data-testid="stAppViewContainer"],
.stApp {
    background: var(--allan-bg) !important;
}

[data-testid="stHeader"],
header[data-testid="stHeader"],
footer,
#MainMenu {
    display: none !important;
}

[data-testid="stAppViewBlockContainer"] {
    padding-top: 0 !important;
}


/* ---------- MAIN CONTENT ---------- */

.block-container {
    width: 100% !important;
    max-width: 1040px !important;
    margin: 0 auto !important;
    padding:
        22px
        clamp(14px, 3vw, 28px)
        150px
        !important;
}

.main,
section.main {
    background: var(--allan-bg) !important;
}


/* ---------- SIDEBAR ---------- */

[data-testid="stSidebar"] {
    background: #0b0e10 !important;
    border-right: 1px solid var(--allan-border) !important;
}

[data-testid="stSidebar"] > div:first-child {
    padding-top: 18px !important;
}

[data-testid="stSidebar"] button {
    min-height: 42px !important;
    border-radius: 11px !important;
    border: 1px solid transparent !important;
    transition:
        background .14s ease,
        border-color .14s ease,
        transform .14s ease !important;
}

[data-testid="stSidebar"] button:hover {
    background: rgba(255,255,255,.045) !important;
    border-color: var(--allan-border) !important;
}

[data-testid="stSidebar"] button:active {
    transform: scale(.985);
}


/* ---------- HEADER ---------- */

.chat-header-bar {
    width: 100% !important;
    box-sizing: border-box !important;

    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;

    gap: 16px !important;

    padding: 13px 16px !important;
    margin: 0 0 24px !important;

    background:
        linear-gradient(
            180deg,
            rgba(19,23,26,.94),
            rgba(12,15,17,.94)
        ) !important;

    border: 1px solid var(--allan-border) !important;
    border-radius: 14px !important;

    box-shadow:
        0 8px 28px rgba(0,0,0,.18) !important;

    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
}

.chat-header-bar h2 {
    margin: 0 !important;
    min-width: 0 !important;

    color: #fff !important;
    font-size: 16px !important;
    line-height: 1.25 !important;
    font-weight: 700 !important;
}


/* ---------- CHAT ---------- */

.chat-msg {
    width: 100% !important;
    box-sizing: border-box !important;
    margin-bottom: 20px !important;
}

.msg-role-user {
    align-items: flex-end !important;
}

.msg-role-ai {
    align-items: flex-start !important;
}

.msg-bubble-user {
    max-width: min(82%, 720px) !important;

    padding: 11px 15px !important;

    background:
        linear-gradient(
            145deg,
            #075e54,
            #075449
        ) !important;

    border: 1px solid rgba(255,255,255,.055) !important;
    border-radius: 17px 17px 5px 17px !important;

    color: #fff !important;

    line-height: 1.52 !important;

    overflow-wrap: anywhere !important;
    word-break: break-word !important;

    box-shadow:
        0 4px 14px rgba(0,0,0,.16) !important;
}

.msg-bubble-ai {
    width: 100% !important;
    max-width: 100% !important;

    color: var(--allan-text) !important;

    line-height: 1.68 !important;
    overflow-wrap: anywhere !important;
}

.msg-ai-name {
    margin-bottom: 7px !important;
    color: var(--allan-accent) !important;
    font-size: 12px !important;
    font-weight: 700 !important;
}


/* ---------- MARKDOWN DA IA ---------- */

.msg-bubble-ai p {
    margin-top: .35em !important;
    margin-bottom: .8em !important;
}

.msg-bubble-ai h1,
.msg-bubble-ai h2,
.msg-bubble-ai h3 {
    color: #fff !important;
    line-height: 1.25 !important;
}

.msg-bubble-ai h1 {
    font-size: 1.55rem !important;
}

.msg-bubble-ai h2 {
    margin-top: 1.35rem !important;
    font-size: 1.25rem !important;
}

.msg-bubble-ai h3 {
    font-size: 1.08rem !important;
}

.msg-bubble-ai ul,
.msg-bubble-ai ol {
    padding-left: 1.3rem !important;
}

.msg-bubble-ai li {
    margin-bottom: .35rem !important;
}


/* ---------- CODE ---------- */

[data-testid="stCodeBlock"],
pre {
    max-width: 100% !important;
    overflow-x: auto !important;
    border-radius: 12px !important;
}

code {
    overflow-wrap: normal !important;
}


/* ---------- TABLES ---------- */

[data-testid="stTable"],
[data-testid="stDataFrame"],
table {
    max-width: 100% !important;
}

.msg-bubble-ai table {
    display: block !important;
    width: 100% !important;
    overflow-x: auto !important;
    border-collapse: collapse !important;
}


/* ---------- ALERTAS ---------- */

[data-testid="stAlert"] {
    border-radius: 12px !important;
    border: 1px solid var(--allan-border) !important;
}


/* ---------- SPINNER ---------- */

[data-testid="stSpinner"] {
    color: var(--allan-muted) !important;
}


/* ---------- CUSTOM COMPONENT ---------- */

iframe {
    max-width: 100% !important;
}

[data-testid="stCustomComponentV1"] {
    width: 100% !important;
    max-width: 100% !important;
}


/* ---------- SCROLL ---------- */

* {
    scrollbar-width: thin;
    scrollbar-color:
        rgba(255,255,255,.16)
        transparent;
}

*::-webkit-scrollbar {
    width: 7px;
    height: 7px;
}

*::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,.16);
    border-radius: 999px;
}

*::-webkit-scrollbar-track {
    background: transparent;
}


/* ---------- TABLET ---------- */

@media (max-width: 900px) {

    .block-container {
        max-width: 100% !important;
        padding:
            16px
            18px
            140px
            !important;
    }

    .chat-header-bar {
        align-items: flex-start !important;
    }

    .msg-bubble-user {
        max-width: 88% !important;
    }
}


/* ---------- PHONE ---------- */

@media (max-width: 640px) {

    .block-container {
        padding:
            10px
            10px
            125px
            !important;
    }

    .chat-header-bar {
        display: block !important;
        padding: 12px 13px !important;
        margin-bottom: 17px !important;
        border-radius: 12px !important;
    }

    .chat-header-bar h2 {
        font-size: 15px !important;
        margin-bottom: 4px !important;
    }

    .chat-header-bar span {
        display: block !important;
        width: 100% !important;
        line-height: 1.35 !important;
        font-size: 11px !important;
    }

    .chat-msg {
        margin-bottom: 16px !important;
    }

    .msg-bubble-user {
        max-width: 92% !important;
        padding: 10px 13px !important;
        font-size: 14px !important;
    }

    .msg-bubble-ai {
        font-size: 14px !important;
        line-height: 1.58 !important;
    }

    [data-testid="stSidebar"] {
        width: min(84vw, 310px) !important;
    }

    [data-testid="stSidebar"] button {
        min-height: 44px !important;
    }
}


/* ---------- VERY SMALL PHONE ---------- */

@media (max-width: 390px) {

    .block-container {
        padding-left: 8px !important;
        padding-right: 8px !important;
    }

    .msg-bubble-user {
        max-width: 95% !important;
    }

}

</style>
""", unsafe_allow_html=True)



# ============================================================
# ROG AI PREMIUM LAYOUT V4
# ============================================================

st.markdown("""
<style>

:root {
    --app-bg: #070910;
    --sidebar-bg: #090d15;

    --surface: #0f1420;
    --surface-2: #141a27;

    --border: rgba(255,255,255,.065);
    --border-hover: rgba(255,255,255,.11);

    --text: #f2f4f8;
    --muted: #7f899b;

    --accent: #7657f5;
    --accent-2: #9b83ff;
    --accent-soft: rgba(118,87,245,.13);
    --accent-border: rgba(118,87,245,.25);

    --success: #2bd9a4;
}

/* APP */

html,
body,
.stApp,
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(
            circle at 52% -15%,
            rgba(118,87,245,.10),
            transparent 34%
        ),
        var(--app-bg) !important;

    color: var(--text) !important;
}

header,
footer,
#MainMenu,
[data-testid="stHeader"] {
    display: none !important;
}

[data-testid="stAppViewBlockContainer"] {
    padding-top: 0 !important;
}

.block-container {
    width: 100% !important;
    max-width: 1180px !important;
    margin: 0 auto !important;

    padding:
        24px
        clamp(20px,3vw,36px)
        145px
        !important;
}

/* SIDEBAR */

[data-testid="stSidebar"] {
    width: 258px !important;

    background:
        linear-gradient(
            180deg,
            #0c111b 0%,
            #080c13 100%
        ) !important;

    border-right:
        1px solid var(--border)
        !important;
}

[data-testid="stSidebar"] > div:first-child {
    padding: 18px 13px !important;
}

/* BRAND */

.rog-brand {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 4px 4px 18px;
}

.rog-logo {
    width: 38px;
    height: 38px;

    display: flex;
    align-items: center;
    justify-content: center;

    border-radius: 12px;

    background:
        linear-gradient(
            135deg,
            #6c4ff5,
            #987cff
        );

    color: white;
    font-size: 17px;
    font-weight: 900;

    box-shadow:
        0 7px 25px
        rgba(118,87,245,.26);
}

.rog-brand-title {
    color: #f5f6fb;
    font-size: 16px;
    font-weight: 800;
}

.rog-brand-subtitle {
    color: var(--muted);
    font-size: 9px;
    margin-top: 4px;
    letter-spacing: .25px;
}

/* PROFILE */

.rog-profile {
    display: flex;
    align-items: center;
    gap: 10px;

    padding: 11px;
    margin: 0 2px 20px;

    border: 1px solid var(--border);
    border-radius: 12px;

    background:
        rgba(255,255,255,.025);
}

.rog-avatar {
    width: 31px;
    height: 31px;

    display: flex;
    align-items: center;
    justify-content: center;

    border-radius: 10px;

    background: var(--accent-soft);
    border: 1px solid var(--accent-border);

    color: #b8aaff;
    font-size: 11px;
    font-weight: 800;
}

.rog-profile-name {
    color: #e7eaf0;
    font-size: 11px;
    font-weight: 700;
}

.rog-profile-status {
    display: flex;
    align-items: center;
    gap: 5px;

    color: var(--success);
    font-size: 8px;
    margin-top: 3px;
}

.rog-profile-dot {
    width: 5px;
    height: 5px;

    border-radius: 999px;
    background: var(--success);

    box-shadow:
        0 0 8px
        rgba(43,217,164,.65);
}

/* SIDEBAR LABEL */

.rog-section-label {
    margin: 14px 7px 8px;

    color: #626c7e;

    font-size: 8px;
    font-weight: 800;

    text-transform: uppercase;
    letter-spacing: 1.2px;
}

/* SIDEBAR BUTTONS */

[data-testid="stSidebar"] .stButton {
    margin-bottom: 5px !important;
}

[data-testid="stSidebar"] button {
    width: 100% !important;
    min-height: 43px !important;

    padding: 0 12px !important;

    border:
        1px solid transparent
        !important;

    border-radius: 10px !important;

    background: transparent !important;

    color: #adb5c4 !important;

    font-size: 10.5px !important;
    font-weight: 600 !important;

    text-align: left !important;
    justify-content: flex-start !important;
}

[data-testid="stSidebar"] button:hover {
    color: white !important;

    background:
        rgba(255,255,255,.04)
        !important;

    border-color:
        var(--border)
        !important;
}

[data-testid="stSidebar"] button[kind="primary"] {
    color: #f0edff !important;

    background:
        var(--accent-soft)
        !important;

    border-color:
        var(--accent-border)
        !important;

    box-shadow:
        inset 3px 0 0
        var(--accent)
        !important;
}

/* TOPBAR */

.rog-topbar {
    width: 100%;

    display: flex;
    align-items: center;
    justify-content: space-between;

    gap: 16px;

    margin-bottom: 26px;
    padding-bottom: 17px;

    border-bottom:
        1px solid var(--border);
}

.rog-agent-info {
    display: flex;
    align-items: center;
    gap: 12px;
}

.rog-agent-icon {
    width: 39px;
    height: 39px;

    display: flex;
    align-items: center;
    justify-content: center;

    border-radius: 11px;

    background: var(--accent-soft);
    border: 1px solid var(--accent-border);

    color: #b9aaff;
    font-size: 15px;
}

.rog-agent-title {
    color: #f5f6f9;
    font-size: 15px;
    font-weight: 750;
}

.rog-agent-description {
    color: var(--muted);
    font-size: 9.5px;
    margin-top: 3px;
}

.rog-online {
    display: flex;
    align-items: center;
    gap: 6px;

    padding: 6px 10px;

    color: #aaf9df;
    font-size: 8.5px;

    border:
        1px solid
        rgba(43,217,164,.12);

    border-radius: 999px;

    background:
        rgba(43,217,164,.05);
}

/* WELCOME */

.rog-welcome {
    max-width: 720px;

    margin:
        clamp(65px,11vh,130px)
        auto 35px;

    text-align: center;
}

.rog-welcome-eyebrow {
    color: #9d8aff;

    font-size: 9px;
    font-weight: 800;

    letter-spacing: 1.1px;
    text-transform: uppercase;

    margin-bottom: 13px;
}

.rog-welcome h1 {
    margin: 0;

    color: white;

    font-size:
        clamp(28px,4vw,40px);

    line-height: 1.08;
    letter-spacing: -1.25px;

    font-weight: 800;
}

.rog-welcome p {
    max-width: 520px;

    margin:
        13px auto 0;

    color: var(--muted);

    font-size: 13px;
    line-height: 1.55;
}

.rog-capabilities {
    display: grid;

    grid-template-columns:
        repeat(4,1fr);

    gap: 8px;

    max-width: 760px;

    margin:
        25px auto 0;
}

.rog-capability {
    padding: 11px 12px;

    text-align: left;

    border:
        1px solid var(--border);

    border-radius: 11px;

    background:
        rgba(255,255,255,.018);
}

.rog-capability-title {
    color: #dce0e8;

    font-size: 9px;
    font-weight: 700;

    margin-bottom: 4px;
}

.rog-capability-text {
    color: #737d8f;

    font-size: 8px;
    line-height: 1.4;
}

/* CHAT */

.chat-msg {
    width: 100%;
    margin-bottom: 21px;
}

.msg-role-user {
    align-items: flex-end;
}

.msg-role-ai {
    align-items: flex-start;
}

.msg-bubble-user {
    max-width:
        min(78%,720px);

    padding: 11px 15px;

    background:
        linear-gradient(
            135deg,
            #6348cc,
            #5037ac
        );

    color: white;

    border-radius:
        15px 15px 4px 15px;

    font-size: 13.5px;
    line-height: 1.5;
}

.msg-bubble-ai {
    width: 100%;
    max-width: 100%;

    padding: 0;

    background: transparent;

    color: #dfe3ea;

    font-size: 13.5px;
    line-height: 1.7;
}

/* COMPONENT */

[data-testid="stCustomComponentV1"] {
    width: 100% !important;
    max-width: 900px !important;

    margin:
        0 auto
        !important;
}

iframe {
    width: 100% !important;
    max-width: 100% !important;
}

/* RESPONSIVE */

@media (max-width:850px) {

    .rog-capabilities {
        grid-template-columns:
            repeat(2,1fr);
    }
}

@media (max-width:650px) {

    .block-container {
        padding:
            12px
            10px
            120px
            !important;
    }

    .rog-online {
        display: none;
    }

    .rog-welcome {
        margin-top: 45px;
    }

    .rog-capabilities {
        grid-template-columns:
            1fr 1fr;
    }

    .msg-bubble-user {
        max-width: 94%;
    }

    [data-testid="stSidebar"] {
        width:
            min(84vw,290px)
            !important;
    }
}

</style>
""", unsafe_allow_html=True)


# --- Sidebar ---

with st.sidebar:

    profile_initial = (
        str(current_profile or "U")[0]
        .upper()
    )

    st.markdown(
        """
        <div class="rog-brand">
            <div class="rog-logo">R</div>

            <div>
                <div class="rog-brand-title">
                    ROG AI
                </div>

                <div class="rog-brand-subtitle">
                    PERSONAL INTELLIGENCE
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="rog-profile">
            <div class="rog-avatar">
                {profile_initial}
            </div>

            <div>
                <div class="rog-profile-name">
                    {current_profile}
                </div>

                <div class="rog-profile-status">
                    <span class="rog-profile-dot"></span>
                    Sistema conectado
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="rog-section-label">
            Assistentes
        </div>
        """,
        unsafe_allow_html=True,
    )

    for a_id, a_data in AGENTS.items():

        is_current = (
            a_id == agent_id
        )

        if st.button(
            f"{a_data['icon']}   {a_data['name']}",
            key=f"nav_{a_id}",
            use_container_width=True,
            type=(
                "primary"
                if is_current
                else "secondary"
            ),
        ):

            st.session_state.current_agent = (
                a_id
            )

            st.rerun()


# --- Funcoes do Pipeline Seguro e Sincrono ---
def ask_llm_sync(agent_id: str, history: list, user_query: str) -> str:
    agent = AGENTS[agent_id]
    model = agent.get("model", "deepseek-chat")

    skills_ctx = ""

    for skill_name in list_available_skills():
        content = load_skill(skill_name)

        if content:
            skills_ctx += (
                f"\n[SKILL {skill_name.upper()}]:\n"
                f"{content}"
            )

    rag_docs = query_rag(
                       user_query,
                       n_results=2,
                       profile=current_profile,
                       agent_id=agent_id,
                       namespaces=allowed_namespaces(
                           current_profile,
                           agent_id,
                       ),
                   )

    sys_content = (
        f"Voce e o agente especialista: {agent['name']}.\n"
        f"Instrucao primaria: {agent['description']}.\n"
        "Responda em Markdown limpo."
    )

    if skills_ctx:
        sys_content += (
            "\n\nHabilidades carregadas:"
            + skills_ctx
        )

    if rag_docs:
        sys_content += (
            "\n\nContexto Base de Conhecimento (RAG):\n"
            + "\n".join(rag_docs)
        )

    messages = [
        {
            "role": "system",
            "content": sys_content
        }
    ]

    for item in history[-20:]:
        messages.append(
            {
                "role": item["role"],
                "content": item["content"]
            }
        )

    messages.append(
        {
            "role": "user",
            "content": user_query
        }
    )

    try:
        return llm_chat(
            model=model,
            messages=messages,
            temperature=0.2,
            max_tokens=2048 if "qwen3" in model.lower() else 4096
        )

    except Exception as e:
        return (
            f"**Erro Sistemico de Roteamento "
            f"(Model: {model}):** {str(e)}"
        )

def load_chat_component():
    p = os.path.join(os.path.dirname(__file__), "frontend", "chat_input", "dist")
    return components.declare_component("rog_chat", path=p) if os.path.exists(p) else None

chat_comp = load_chat_component()
if not chat_comp:
    st.error("Erro Critico: Frontend nao compilado. Execute setup.ps1.")
    st.stop()

# --- Cabecalho do chat ---

st.markdown(
    f"""
    <div class="rog-topbar">

        <div class="rog-agent-info">

            <div class="rog-agent-icon">
                {agent["icon"]}
            </div>

            <div>
                <div class="rog-agent-title">
                    {agent["name"]}
                </div>

                <div class="rog-agent-description">
                    {agent["description"]}
                </div>
            </div>

        </div>

        <div class="rog-online">
            <span class="rog-profile-dot"></span>
            Online
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


if not st.session_state.conversations.get(
    agent_id,
    [],
):

    st.markdown(
        f"""
        <div class="rog-welcome">

            <div class="rog-welcome-eyebrow">
                ROG AI WORKSPACE
            </div>

            <h1>
                Como posso ajudar, {current_profile}?
            </h1>

            <p>
                Converse naturalmente com o ROG AI
                ou escolha um assistente especializado
                na barra lateral.
            </p>

            <div class="rog-capabilities">

                <div class="rog-capability">
                    <div class="rog-capability-title">
                        ?? Finan?as
                    </div>

                    <div class="rog-capability-text">
                        Or?amento, metas e planejamento.
                    </div>
                </div>

                <div class="rog-capability">
                    <div class="rog-capability-title">
                        ?? Tecnologia
                    </div>

                    <div class="rog-capability-text">
                        C?digo, hardware e software.
                    </div>
                </div>

                <div class="rog-capability">
                    <div class="rog-capability-title">
                        ?? Organiza??o
                    </div>

                    <div class="rog-capability-text">
                        Rotina, decis?es e projetos.
                    </div>
                </div>

                <div class="rog-capability">
                    <div class="rog-capability-title">
                        ???? English
                    </div>

                    <div class="rog-capability-text">
                        Conversa??o e desenvolvimento.
                    </div>
                </div>

            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


# --- Historico da conversa ---
for message in st.session_state.conversations.get(agent_id, []):
    role = message.get("role", "")
    content = message.get("content", "")

    if role == "user":
        with st.chat_message("user"):
            st.markdown(content)

    elif role == "assistant":
        with st.chat_message("assistant"):

            runtime = message.get("runtime", {})

            selected_agent = runtime.get(
                "selected_agent",
                agent_id
            )

            selected_name = runtime.get(
                "agent_name",
                agent["name"]
            )

            selected_model = runtime.get(
                "model",
                agent.get("model", "")
            )

            if agent_id == "orchestrator" and selected_agent != "orchestrator":
                st.caption(
                    f"ROG AI Core -> {selected_name} | {selected_model}"
                )
            else:
                st.caption(
                    f"{selected_name} | {selected_model}"
                )

            st.markdown(content)

# Key global impede re-montagem ao trocar de agente
comp_value = chat_comp(key="rog_global_composer")

if comp_value and isinstance(comp_value, dict):
    print("DEBUG_EVENT_RECEIVED:", comp_value, flush=True)
    eid = comp_value.get("event_id")
    etype = comp_value.get("type")
    
    # Event Deduplication Control
    if eid and eid not in st.session_state.processed_events:
        st.session_state.processed_events.add(eid)
        if len(st.session_state.processed_events) > 100:
            st.session_state.processed_events.clear() # Mantem pegada de memoria leve
            
        final_query = None
        
        if etype == "send":
            txt = comp_value.get("text", "").strip()
            files = comp_value.get("files", [])
            ctx_attachments = []
            
            for f in files:
                try:
                    filename = f.get("name", "arquivo")
                    mime_type = f.get("type", "")
                    file_size = f.get("size", 0)

                    b = base64.b64decode(f["data"])

                    extraction = extract_document_text(
                        file_bytes=b,
                        filename=filename,
                        mime_type=mime_type,
                    )

                    if not extraction.get("success"):
                        error_message = extraction.get(
                            "error",
                            "Falha desconhecida na extracao."
                        )

                        ctx_attachments.append(
                            f"[Anexo nao processado: {filename} | {error_message}]"
                        )

                        continue

                    extracted_text = extraction.get("text", "").strip()
                    f_hash = extraction.get("file_hash") or calculate_file_sha256(b)

                    rag_result = add_document_to_rag(
                                         f_hash,
                                         f"Documento enviado: {f['name']}",
                                         {
                                             "profile": str(
                                                 current_profile
                                             ).strip().lower(),
                                 
                                             "agent_id":
                                                 agent_id,
                                 
                                             "namespace":
                                                 write_namespace(
                                                     current_profile,
                                                     agent_id,
                                                     shared_finance=False,
                                                 ),
                                         },
                                     )

                    if not rag_result.get("success", False):
                        ctx_attachments.append(
                            f"[Falha ao indexar no RAG: {filename}]"
                        )
                        continue

                    ctx_attachments.append(
                        f"[Anexo processado: {filename} | "
                        f"{rag_result.get('chunks', 0)} chunks | "
                        f"metodo={extraction.get('method')}]"
                    )

                except Exception as e:
                    ctx_attachments.append(
                        f"[Falha ao ler {f.get('name', 'arquivo')}: {e}]"
                    )
                    
            if ctx_attachments:
                final_query = "\n".join(ctx_attachments) + "\n\n" + (txt if txt else "Verifique os anexos processados.")
            else:
                final_query = txt if txt else None

        elif etype == "audio":
            try:
                b = base64.b64decode(comp_value.get("audio", ""))
                transcript = transcribe_audio_bytes(b)
                if transcript:
                    final_query = f"??? *Transcricao de audio:*\n{transcript.strip()}"
            except Exception as e:
                st.error(f"Erro Whisper: {e}")

        # Se houver query valida processada, executa pipeline LLM
        if final_query:
            print("DEBUG_FINAL_QUERY:", repr(final_query), flush=True)

            # ====================================================
            # MEMORY ENGINE V2 - COMMANDS
            # ====================================================

            memory_command_result = None
            auto_memory_result = None

            try:
                memory_command_result = _memory_commands.process(
                    profile=current_profile,
                    user_text=final_query,
                )

            except Exception as memory_command_error:
                print(
                    "MEMORY_COMMAND_ERROR:",
                    repr(memory_command_error),
                    flush=True,
                )

            # ----------------------------------------------------
            # Comando explicito de memoria
            # ----------------------------------------------------

            if (
                memory_command_result
                and memory_command_result.get("handled")
            ):
                command = memory_command_result.get("command")

                if command == "REMEMBER":
                    inner = memory_command_result.get(
                        "result",
                        {},
                    )

                    action = inner.get(
                        "action",
                        "SKIP",
                    )

                    if memory_command_result.get("success"):

                        if action == "UPDATE":
                            command_answer = "Memoria atualizada."

                        elif action == "SKIP":
                            command_answer = (
                                "Isso ja estava registrado na memoria."
                            )

                        else:
                            command_answer = "Memoria salva."

                    else:
                        command_answer = (
                            "Nao consegui salvar essa memoria."
                        )

                elif command == "FORGET":
                    forgotten = memory_command_result.get(
                        "forgotten",
                        0,
                    )

                    if forgotten > 0:
                        command_answer = (
                            f"Removi {forgotten} memoria(s) relacionada(s)."
                        )
                    else:
                        command_answer = (
                            "Nao encontrei memoria correspondente "
                            "para remover."
                        )

                else:
                    command_answer = (
                        "Comando de memoria processado."
                    )

                st.session_state.conversations[agent_id].append(
                    {
                        "role": "user",
                        "content": final_query,
                    }
                )

                st.session_state.conversations[agent_id].append(
                    {
                        "role": "assistant",
                        "content": command_answer,
                        "runtime": {
                            "requested_agent": agent_id,
                            "selected_agent": "memory",
                            "agent_name": "Memory Engine",
                            "model": "memory-v2",
                            "provider": "local+supabase",
                            "fallback": False,
                            "memory_command": command,
                        },
                    }
                )

                print(
                    "MEMORY_COMMAND_HANDLED:",
                    command,
                    flush=True,
                )

                st.rerun()

            # ====================================================
            # MEMORY ENGINE V2 - AUTO MEMORY
            # ====================================================

            if should_consider_auto_memory(final_query):

                try:
                    auto_memory_result = (
                        _memory_consolidator.process_text(
                            profile=current_profile,
                            user_text=final_query,
                            source="automatic_chat",
                        )
                    )

                    print(
                        "AUTO_MEMORY_RESULT:",
                        auto_memory_result.get("action"),
                        flush=True,
                    )

                except Exception as auto_memory_error:
                    print(
                        "AUTO_MEMORY_ERROR:",
                        repr(auto_memory_error),
                        flush=True,
                    )

            # ====================================================
            # PIPELINE NORMAL
            # ====================================================

            st.session_state.conversations[agent_id].append(
                {
                    "role": "user",
                    "content": final_query
                }
            )

            with st.spinner(f"{agent['name']} analisando..."):
                print(
                    "DEBUG_RUNTIME_REQUEST:",
                    agent_id,
                    flush=True
                )

                try:
                    runtime_result = execute_agent(
                        agent_id=agent_id,
                        history=st.session_state.conversations[agent_id][:-1],
                        user_query=final_query,
                        profile=current_profile,
                    )

                    ans = runtime_result["answer"]

                    selected_agent = runtime_result["selected_agent"]
                    selected_name = runtime_result["agent_name"]
                    selected_model = runtime_result["model"]

                    print(
                        "DEBUG_RUNTIME_SELECTED:",
                        selected_agent,
                        selected_name,
                        selected_model,
                        flush=True
                    )

                except Exception as runtime_error:
                    print(
                        "DEBUG_RUNTIME_FALLBACK:",
                        repr(runtime_error),
                        flush=True
                    )

                    ans = ask_llm_sync(
                        agent_id,
                        st.session_state.conversations[agent_id][:-1],
                        final_query
                    )

                    selected_agent = agent_id
                    selected_name = AGENTS[agent_id]["name"]
                    selected_model = AGENTS[agent_id]["model"]

            assistant_message = {
                "role": "assistant",
                "content": ans,
                "runtime": {
                    "requested_agent": agent_id,
                    "selected_agent": selected_agent,
                    "agent_name": selected_name,
                    "model": selected_model,
                }
            }

            st.session_state.conversations[agent_id].append(
                assistant_message
            )

            pm.save(
                {
                    profile_key:
                        st.session_state.long_memory
                }
            )

            st.rerun()