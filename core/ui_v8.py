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
:root{color-scheme:dark;--rog-bg:#030407;--rog-surface:#090b11;--rog-surface2:#0f121b;--rog-line:rgba(255,255,255,.09);--rog-text:#f7f7fb;--rog-muted:#9298a8;--rog-dim:#686f80;--rog-accent:#8a68ff;--rog-accent2:#b29cff;--rog-success:#51ddb2}
html,body,.stApp,[data-testid="stAppViewContainer"]{background:radial-gradient(900px 420px at 65% -180px,rgba(124,87,255,.18),transparent 72%),var(--rog-bg)!important;color:var(--rog-text)!important}body{font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important}#MainMenu,footer,.stDeployButton,[data-testid="stToolbar"]{display:none!important}[data-testid="stHeader"]{height:0!important;background:transparent!important}[data-testid="stSidebarCollapsedControl"]{position:fixed!important;top:10px!important;left:10px!important;z-index:999!important}[data-testid="stAppViewBlockContainer"]{padding-top:0!important}.block-container{max-width:1120px!important;padding:24px clamp(20px,4vw,54px) 140px!important}a{color:var(--rog-accent2)!important}*:focus-visible{outline:2px solid var(--rog-accent2)!important;outline-offset:2px!important}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#090b10,#050609)!important;border-right:1px solid var(--rog-line)!important;min-width:286px!important}[data-testid="stSidebar"]>div:first-child{padding:18px 13px 22px!important}[data-testid="stSidebar"] button{width:100%!important;min-height:43px!important;justify-content:flex-start!important;border-radius:12px!important;border:1px solid transparent!important;background:transparent!important;color:#b7bdcb!important;font-size:12px!important;font-weight:550!important;transition:background .16s ease,border-color .16s ease,color .16s ease,transform .16s ease!important}[data-testid="stSidebar"] button:hover{background:rgba(255,255,255,.055)!important;border-color:var(--rog-line)!important;color:white!important}[data-testid="stSidebar"] button:active{transform:scale(.985)}[data-testid="stSidebar"] button[kind="primary"]{background:linear-gradient(90deg,rgba(126,91,255,.20),rgba(126,91,255,.07))!important;border-color:rgba(142,108,255,.34)!important;color:#faf8ff!important;box-shadow:inset 3px 0 0 var(--rog-accent)!important}[data-testid="stSidebar"] hr{border-color:var(--rog-line)!important;margin:15px 4px!important}
.rog-brand{display:flex;align-items:center;gap:12px;padding:3px 4px 18px}.rog-logo{width:42px;height:42px;border-radius:13px;display:grid;place-items:center;font-weight:950;letter-spacing:-1px;background:linear-gradient(145deg,#5e3ee4,#9d7cff);box-shadow:0 10px 32px rgba(118,83,255,.3),inset 0 1px rgba(255,255,255,.2)}.rog-brand-title{font-weight:880;font-size:16px}.rog-brand-sub{font-size:8px;color:var(--rog-muted);letter-spacing:1.2px;margin-top:3px}.rog-profile{padding:11px 12px;border-radius:13px;border:1px solid var(--rog-line);background:rgba(255,255,255,.027);margin:0 2px 18px}.rog-profile-line{display:flex;align-items:center;gap:9px}.rog-avatar{width:27px;height:27px;border-radius:9px;display:grid;place-items:center;background:rgba(138,104,255,.16);color:#d8ceff;font-size:11px;font-weight:800}.rog-profile strong{font-size:11px}.rog-profile span{display:block;color:var(--rog-success);font-size:8px;margin-top:2px}.rog-section{color:#737b8e;font-size:8px;text-transform:uppercase;letter-spacing:1.35px;font-weight:850;margin:15px 7px 8px}
.rog-hero{position:sticky;top:0;z-index:5;padding:5px 0 18px;margin-bottom:22px;border-bottom:1px solid var(--rog-line);background:linear-gradient(180deg,var(--rog-bg) 80%,transparent)}.rog-hero-row{display:flex;align-items:center;gap:13px}.rog-agent-icon{width:44px;height:44px;border-radius:14px;display:grid;place-items:center;background:linear-gradient(145deg,rgba(133,98,255,.22),rgba(133,98,255,.08));border:1px solid rgba(145,112,255,.32);color:#d0c3ff;font-size:16px;font-weight:850}.rog-agent-name{font-size:15px;font-weight:820}.rog-agent-desc{color:var(--rog-muted);font-size:10px;margin-top:3px}.rog-status{margin-left:auto;display:flex;align-items:center;gap:6px;color:#b6f5e2;font-size:9px;padding:6px 10px;border:1px solid rgba(81,221,178,.18);background:rgba(81,221,178,.06);border-radius:999px}.rog-status-dot{width:6px;height:6px;border-radius:50%;background:var(--rog-success)}.rog-status.is-busy{color:#ddd2ff;border-color:rgba(138,104,255,.25);background:rgba(138,104,255,.09)}.rog-status.is-busy .rog-status-dot{background:var(--rog-accent2);animation:rog-pulse 1.1s infinite}@keyframes rog-pulse{50%{opacity:.35}}
.rog-welcome{display:grid;place-items:center;text-align:center;min-height:34vh;padding:32px 20px 20px}.rog-welcome-orb{width:68px;height:68px;border-radius:21px;display:grid;place-items:center;margin-bottom:18px;background:linear-gradient(145deg,rgba(132,96,255,.25),rgba(132,96,255,.07));border:1px solid rgba(143,110,255,.3);box-shadow:0 18px 60px rgba(89,54,205,.14);font-size:23px}.rog-eyebrow{font-size:9px;color:#9f8cff;text-transform:uppercase;letter-spacing:1.5px;font-weight:800;margin-bottom:8px}.rog-welcome h2{margin:0;font-size:clamp(26px,4vw,40px);letter-spacing:-1.4px;line-height:1.08}.rog-welcome p{color:var(--rog-muted);max-width:570px;font-size:13px;line-height:1.65;margin:13px auto 0}
[data-testid="stChatMessage"]{max-width:880px;margin:0 auto 12px!important;padding:0!important;background:transparent!important;gap:10px!important}[data-testid="stChatMessageContent"]{border:1px solid var(--rog-line);border-radius:16px;padding:13px 16px!important;background:rgba(15,18,27,.82);font-size:14px;line-height:1.68;overflow-wrap:anywhere}[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"]{background:linear-gradient(145deg,rgba(109,76,224,.24),rgba(61,43,126,.2));border-color:rgba(140,105,255,.25)}[data-testid="stChatMessageContent"] p:last-child{margin-bottom:0}
[data-testid="stChatInput"]{border-radius:18px!important;border:1px solid rgba(148,118,255,.35)!important;background:rgba(13,16,24,.98)!important;box-shadow:0 16px 56px rgba(0,0,0,.48)!important;min-height:58px!important}[data-testid="stChatInput"]:focus-within{border-color:var(--rog-accent2)!important;box-shadow:0 16px 56px rgba(0,0,0,.5),0 0 0 3px rgba(138,104,255,.12)!important}[data-testid="stBottom"]{background:linear-gradient(180deg,transparent,var(--rog-bg) 28%)!important;padding-top:28px!important}[data-testid="stChatInput"] button{color:#c7b9ff!important}
[data-testid="stAlert"],[data-testid="stVerticalBlockBorderWrapper"]>div{border-radius:16px!important;border-color:var(--rog-line)!important}.stButton>button{border-radius:12px!important;transition:transform .13s ease,border-color .13s ease!important}.stButton>button[kind="primary"],button[kind="primaryFormSubmit"]{background:linear-gradient(135deg,#6848ec,#9272ff)!important;border-color:#9d83ff!important;color:#fff!important}.stButton>button:hover{border-color:rgba(145,112,255,.5)!important}.stButton>button:active{transform:scale(.985)}.stButton>button:disabled{opacity:.48!important;cursor:not-allowed!important}.rog-quick-label{text-align:center;color:var(--rog-dim);font-size:9px;text-transform:uppercase;letter-spacing:1.1px;margin:2px 0 -3px}
@media(max-width:760px){.block-container{padding:54px 10px 116px!important}.rog-hero{padding-top:3px;margin-bottom:14px}.rog-agent-desc{max-width:47vw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.rog-status{padding:5px 7px}.rog-status span:last-child{display:none}.rog-welcome{min-height:25vh;padding:18px 6px 12px}.rog-welcome-orb{width:58px;height:58px;border-radius:18px}.rog-welcome p{font-size:12px}[data-testid="stSidebar"]{width:min(88vw,310px)!important}[data-testid="stChatMessageContent"]{padding:11px 13px!important;font-size:13px}.rog-quick-label{margin-top:8px}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
</style>''', unsafe_allow_html=True)


def render_brand() -> None:
    st.markdown('<div class="rog-brand"><div class="rog-logo" aria-hidden="true">R</div><div><div class="rog-brand-title">ROG AI</div><div class="rog-brand-sub">FAMILY INTELLIGENCE</div></div></div>', unsafe_allow_html=True)


def render_profile(profile: str) -> None:
    label = PROFILE_LABELS.get(str(profile or "").lower(), str(profile or "").title())
    st.markdown(f'<div class="rog-profile"><div class="rog-profile-line"><div class="rog-avatar" aria-hidden="true">{html.escape(label[:1].upper() or "?")}</div><div><strong>{html.escape(label)}</strong><span>● Workspace privado</span></div></div></div>', unsafe_allow_html=True)


def render_section(text: str) -> None:
    st.markdown(f'<div class="rog-section">{html.escape(text)}</div>', unsafe_allow_html=True)


def render_agent_header(agent_id: str, *, busy: bool = False) -> None:
    icon, name, desc = AGENT_META.get(agent_id, AGENT_META["orchestrator"])
    status, state_class = ("Processando", " is-busy") if busy else ("Pronto", "")
    st.markdown(f'<div class="rog-hero"><div class="rog-hero-row"><div class="rog-agent-icon" aria-hidden="true">{html.escape(icon)}</div><div><div class="rog-agent-name">{html.escape(name)}</div><div class="rog-agent-desc">{html.escape(desc)}</div></div><div class="rog-status{state_class}" role="status"><span class="rog-status-dot"></span><span>{status}</span></div></div></div>', unsafe_allow_html=True)


def render_welcome(agent_id: str, profile: str) -> None:
    icon, name, _ = AGENT_META.get(agent_id, AGENT_META["orchestrator"])
    person = PROFILE_LABELS.get(str(profile or "").lower(), str(profile or "").title())
    st.markdown(f'<div class="rog-welcome"><div class="rog-welcome-orb" aria-hidden="true">{html.escape(icon)}</div><div class="rog-eyebrow">{html.escape(name)}</div><h2>Como posso ajudar, {html.escape(person)}?</h2><p>Converse com seu assistente ou use uma ação abaixo. Seus chats, memórias e documentos respeitam o workspace do perfil atual.</p></div>', unsafe_allow_html=True)
