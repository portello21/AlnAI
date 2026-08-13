from __future__ import annotations

import html
import streamlit as st

AGENT_META = {
    "orchestrator": ("✦", "ROG AI Core", "Orquestração inteligente e delegação automática"),
    "personal": ("◎", "Pessoal", "Rotina, decisões e organização"),
    "finance": ("◈", "Finanças", "Planejamento e análise financeira"),
    "tech": ("⌘", "Tecnologia", "Código, hardware e sistemas"),
    "coach": ("△", "Coach", "Treino, performance e hábitos"),
    "business": ("◇", "Negócios", "Projetos, estratégia e receita"),
    "english": ("A", "English", "Conversação, escrita e fluência"),
    "document": ("▤", "Documentos", "Arquivos, OCR e RAG"),
}

PROFILE_LABELS = {"allan": "Allan", "beatriz": "Beatriz", "natan": "Natan", "tainan": "Tainan"}


def inject_design_system() -> None:
    st.markdown(r'''<style>
:root{--rog-bg:#070910;--rog-panel:#0d121b;--rog-panel2:#121925;--rog-line:rgba(255,255,255,.075);--rog-text:#f5f7fb;--rog-muted:#8993a4;--rog-accent:#7c5cff;--rog-accent2:#9c86ff;--rog-success:#35d7a2}
html,body,.stApp,[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 50% -15%,rgba(124,92,255,.12),transparent 35%),var(--rog-bg)!important;color:var(--rog-text)!important}#MainMenu,footer,[data-testid="stHeader"]{display:none!important}[data-testid="stAppViewBlockContainer"]{padding-top:0!important}.block-container{max-width:1160px!important;padding:22px clamp(14px,3vw,34px) 132px!important}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0b1018,#080b11)!important;border-right:1px solid var(--rog-line)!important}[data-testid="stSidebar"]>div:first-child{padding:16px 12px!important}[data-testid="stSidebar"] button{width:100%!important;min-height:42px!important;justify-content:flex-start!important;border-radius:11px!important;border:1px solid transparent!important;background:transparent!important;color:#b7bfcc!important;font-size:12px!important}[data-testid="stSidebar"] button:hover{background:rgba(255,255,255,.045)!important;border-color:var(--rog-line)!important;color:white!important}[data-testid="stSidebar"] button[kind="primary"]{background:rgba(124,92,255,.14)!important;border-color:rgba(124,92,255,.3)!important;color:#f4f1ff!important;box-shadow:inset 3px 0 0 var(--rog-accent)!important}
.rog-brand{display:flex;align-items:center;gap:11px;padding:4px 4px 17px}.rog-logo{width:39px;height:39px;border-radius:12px;display:grid;place-items:center;font-weight:900;background:linear-gradient(135deg,#684bf0,#9b82ff);box-shadow:0 8px 28px rgba(118,87,245,.27)}.rog-brand-title{font-weight:850;font-size:16px}.rog-brand-sub{font-size:9px;color:var(--rog-muted);letter-spacing:.7px;margin-top:2px}.rog-profile{padding:10px 12px;border-radius:13px;border:1px solid var(--rog-line);background:rgba(255,255,255,.025);margin:2px 2px 17px}.rog-profile strong{font-size:11px}.rog-profile span{display:block;color:var(--rog-success);font-size:8px;margin-top:3px}.rog-section{color:#697386;font-size:8px;text-transform:uppercase;letter-spacing:1.2px;font-weight:850;margin:14px 6px 8px}
.rog-hero{padding:0 0 17px;margin-bottom:23px;border-bottom:1px solid var(--rog-line)}.rog-hero-row{display:flex;align-items:center;gap:12px}.rog-agent-icon{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;background:rgba(124,92,255,.14);border:1px solid rgba(124,92,255,.28);color:#c3b7ff;font-size:15px;font-weight:850}.rog-agent-name{font-size:15px;font-weight:800}.rog-agent-desc{color:var(--rog-muted);font-size:10px;margin-top:3px}.rog-online{margin-left:auto;color:#aaf4dc;font-size:9px;padding:6px 10px;border:1px solid rgba(53,215,162,.15);background:rgba(53,215,162,.055);border-radius:999px}
.rog-welcome{display:grid;place-items:center;text-align:center;min-height:38vh;padding:28px}.rog-welcome-orb{width:64px;height:64px;border-radius:20px;display:grid;place-items:center;margin-bottom:15px;background:linear-gradient(135deg,rgba(124,92,255,.22),rgba(156,134,255,.09));border:1px solid rgba(124,92,255,.27);font-size:22px}.rog-welcome h2{margin:0;font-size:clamp(25px,4vw,38px);letter-spacing:-1px}.rog-welcome p{color:var(--rog-muted);max-width:560px;font-size:13px;line-height:1.6}
[data-testid="stChatMessage"]{background:transparent!important;padding:.4rem 0!important}[data-testid="stChatMessageContent"]{font-size:14px;line-height:1.68}[data-testid="stChatInput"]{border-radius:17px!important;border:1px solid rgba(124,92,255,.24)!important;background:#0d121b!important;box-shadow:0 12px 44px rgba(0,0,0,.32)}[data-testid="stCustomComponentV1"]{width:100%!important;max-width:920px!important;margin:0 auto!important}iframe{max-width:100%!important}[data-testid="stAlert"]{border-radius:12px!important;border:1px solid var(--rog-line)!important}
@media(max-width:700px){.block-container{padding:10px 9px 115px!important}.rog-online{display:none}.rog-hero{margin-bottom:15px}.rog-agent-desc{max-width:230px}.rog-welcome{min-height:30vh;padding:18px 6px}[data-testid="stSidebar"]{width:min(86vw,300px)!important}}
</style>''', unsafe_allow_html=True)


def render_brand() -> None:
    st.markdown('<div class="rog-brand"><div class="rog-logo">R</div><div><div class="rog-brand-title">ROG AI</div><div class="rog-brand-sub">FAMILY INTELLIGENCE</div></div></div>', unsafe_allow_html=True)


def render_profile(profile: str) -> None:
    label = PROFILE_LABELS.get(str(profile or "").lower(), str(profile or "").title())
    st.markdown(f'<div class="rog-profile"><strong>{html.escape(label)}</strong><span>● Workspace privado</span></div>', unsafe_allow_html=True)


def render_agent_header(agent_id: str) -> None:
    icon, name, desc = AGENT_META.get(agent_id, AGENT_META["orchestrator"])
    st.markdown(f'<div class="rog-hero"><div class="rog-hero-row"><div class="rog-agent-icon">{icon}</div><div><div class="rog-agent-name">{html.escape(name)}</div><div class="rog-agent-desc">{html.escape(desc)}</div></div><div class="rog-online">● Online</div></div></div>', unsafe_allow_html=True)


def render_welcome(agent_id: str, profile: str) -> None:
    icon, name, _ = AGENT_META.get(agent_id, AGENT_META["orchestrator"])
    person = PROFILE_LABELS.get(str(profile or "").lower(), str(profile or "").title())
    st.markdown(f'<div class="rog-welcome"><div class="rog-welcome-orb">{icon}</div><h2>Como posso ajudar, {html.escape(person)}?</h2><p>Você está no <strong>{html.escape(name)}</strong>. Envie uma mensagem, anexe um arquivo ou escolha outro especialista na barra lateral.</p></div>', unsafe_allow_html=True)
