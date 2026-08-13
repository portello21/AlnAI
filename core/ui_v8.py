from __future__ import annotations

import html
import streamlit as st


AGENT_META = {
    "orchestrator": ("✦", "ROG AI Core", "Orquestração inteligente"),
    "personal": ("◎", "Pessoal", "Rotina e organização"),
    "finance": ("◈", "Finanças", "Planejamento financeiro"),
    "tech": ("⌘", "Tecnologia", "Código e sistemas"),
    "coach": ("△", "Coach", "Treino e performance"),
    "business": ("◇", "Negócios", "Projetos e estratégia"),
    "english": ("A", "English", "Conversação e estudo"),
    "documents": ("▤", "Documentos", "Arquivos e RAG"),
}

PROFILE_LABELS = {
    "allan": "Allan",
    "beatriz": "Beatriz",
    "natan": "Natan",
    "tainan": "Tainan",
}


def inject_design_system() -> None:
    st.markdown(
        r'''<style>
        :root {
          --rog-bg:#07090d; --rog-panel:#0d1117; --rog-panel2:#111720;
          --rog-line:rgba(255,255,255,.075); --rog-text:#f5f7fb;
          --rog-muted:#8e98a8; --rog-accent:#8b5cf6; --rog-accent2:#22d3ee;
          --rog-success:#34d399; --rog-radius:18px;
        }
        html,body,[data-testid="stAppViewContainer"]{background:var(--rog-bg)!important;color:var(--rog-text)!important}
        [data-testid="stHeader"]{background:rgba(7,9,13,.72)!important;backdrop-filter:blur(18px);border-bottom:1px solid var(--rog-line)}
        [data-testid="stSidebar"]{background:#090c11!important;border-right:1px solid var(--rog-line)}
        [data-testid="stSidebar"]>div:first-child{padding-top:1rem}
        .block-container{max-width:1120px!important;padding-top:1.4rem!important;padding-bottom:8rem!important}
        #MainMenu,footer{visibility:hidden}
        h1,h2,h3,p{letter-spacing:-.01em}
        .rog-brand{display:flex;align-items:center;gap:12px;padding:8px 4px 18px}
        .rog-logo{width:38px;height:38px;border-radius:13px;display:grid;place-items:center;font-weight:900;background:linear-gradient(135deg,var(--rog-accent),var(--rog-accent2));box-shadow:0 8px 30px rgba(139,92,246,.28)}
        .rog-brand-title{font-weight:800;font-size:1.05rem}.rog-brand-sub{color:var(--rog-muted);font-size:.72rem;margin-top:1px}
        .rog-hero{padding:18px 20px;border:1px solid var(--rog-line);border-radius:22px;background:linear-gradient(145deg,rgba(139,92,246,.10),rgba(34,211,238,.035) 48%,rgba(255,255,255,.018));box-shadow:0 18px 70px rgba(0,0,0,.24);margin-bottom:18px}
        .rog-hero-row{display:flex;align-items:center;gap:14px}.rog-agent-icon{width:46px;height:46px;border-radius:15px;display:grid;place-items:center;background:rgba(139,92,246,.13);border:1px solid rgba(139,92,246,.24);font-size:1.25rem;font-weight:800}
        .rog-agent-name{font-size:1.08rem;font-weight:800}.rog-agent-desc{color:var(--rog-muted);font-size:.82rem;margin-top:2px}.rog-online{margin-left:auto;color:var(--rog-success);font-size:.76rem;padding:6px 10px;border:1px solid rgba(52,211,153,.18);background:rgba(52,211,153,.06);border-radius:999px}
        [data-testid="stChatMessage"]{background:transparent!important;border:none!important;padding:.35rem 0!important}
        [data-testid="stChatMessageContent"]{border:1px solid var(--rog-line);border-radius:18px;padding:13px 15px;background:var(--rog-panel)!important;box-shadow:0 7px 28px rgba(0,0,0,.12)}
        [data-testid="stChatInput"]{border-radius:18px!important;border:1px solid rgba(139,92,246,.22)!important;background:#0d1117!important;box-shadow:0 12px 44px rgba(0,0,0,.35)}
        [data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea,[data-testid="stSelectbox"]>div>div{background:#0d1117!important;border-color:var(--rog-line)!important;color:var(--rog-text)!important;border-radius:13px!important}
        .stButton>button{width:100%;border-radius:13px!important;border:1px solid var(--rog-line)!important;background:#0e131b!important;color:var(--rog-text)!important;min-height:42px;transition:.16s ease}
        .stButton>button:hover{border-color:rgba(139,92,246,.42)!important;background:#131927!important;transform:translateY(-1px)}
        .stButton>button[kind="primary"]{background:linear-gradient(135deg,#7c3aed,#6d28d9)!important;border-color:transparent!important;box-shadow:0 8px 26px rgba(124,58,237,.24)}
        [data-testid="stFileUploader"]{background:#0d1117;border:1px dashed rgba(139,92,246,.28);border-radius:16px;padding:8px}
        .rog-profile{padding:10px 12px;border-radius:14px;border:1px solid var(--rog-line);background:rgba(255,255,255,.025);margin:8px 0 12px}.rog-profile strong{font-size:.9rem}.rog-profile span{display:block;color:var(--rog-muted);font-size:.72rem;margin-top:2px}
        .rog-section{color:#697386;font-size:.67rem;text-transform:uppercase;letter-spacing:.12em;font-weight:800;margin:15px 3px 7px}
        .rog-welcome{display:grid;place-items:center;text-align:center;min-height:34vh;padding:30px}.rog-welcome-orb{width:62px;height:62px;border-radius:20px;display:grid;place-items:center;margin-bottom:15px;background:linear-gradient(135deg,rgba(139,92,246,.22),rgba(34,211,238,.11));border:1px solid rgba(139,92,246,.25);font-size:1.5rem}.rog-welcome h2{margin:0;font-size:1.35rem}.rog-welcome p{color:var(--rog-muted);max-width:520px;font-size:.9rem}
        @media(max-width:700px){.block-container{padding-left:.8rem!important;padding-right:.8rem!important;padding-top:.7rem!important}.rog-hero{padding:14px}.rog-online{display:none}.rog-agent-icon{width:40px;height:40px}.rog-welcome{min-height:28vh;padding:18px 8px}}
        </style>''',
        unsafe_allow_html=True,
    )


def render_brand() -> None:
    st.markdown('<div class="rog-brand"><div class="rog-logo">R</div><div><div class="rog-brand-title">ROG AI</div><div class="rog-brand-sub">Family Intelligence</div></div></div>', unsafe_allow_html=True)


def render_profile(profile: str) -> None:
    key = str(profile or "").lower()
    label = PROFILE_LABELS.get(key, str(profile).title())
    st.markdown(f'<div class="rog-profile"><strong>{html.escape(label)}</strong><span>Workspace privado · dispositivo atual</span></div>', unsafe_allow_html=True)


def render_agent_header(agent_id: str) -> None:
    icon, name, desc = AGENT_META.get(agent_id, AGENT_META["orchestrator"])
    st.markdown(f'<div class="rog-hero"><div class="rog-hero-row"><div class="rog-agent-icon">{icon}</div><div><div class="rog-agent-name">{html.escape(name)}</div><div class="rog-agent-desc">{html.escape(desc)}</div></div><div class="rog-online">● Online</div></div></div>', unsafe_allow_html=True)


def render_welcome(agent_id: str, profile: str) -> None:
    icon, name, _ = AGENT_META.get(agent_id, AGENT_META["orchestrator"])
    person = PROFILE_LABELS.get(str(profile).lower(), str(profile).title())
    st.markdown(f'<div class="rog-welcome"><div class="rog-welcome-orb">{icon}</div><h2>Olá, {html.escape(person)}</h2><p>Você está no <strong>{html.escape(name)}</strong>. Envie uma mensagem, anexe um arquivo ou escolha outro especialista na barra lateral.</p></div>', unsafe_allow_html=True)
