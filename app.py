import html
import json
import os
import re
import time
from typing import Any

import requests
import streamlit as st
import streamlit.components.v2 as components

# ============================================================
# CONFIGURAÇÃO DE SEGURANÇA E PÁGINA
# ============================================================

st.set_page_config(
    page_title="Allan AI - Core",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
MEMORY_FILE = "long_term_memory.json"
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "Allan2026@Pass")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# ============================================================
# LOGIN
# ============================================================

if not st.session_state.authenticated:
    st.markdown("""
    <style>
    .stApp { background-color: #0b141a !important; color: #e9edef !important; }
    .login-box { max-width: 400px; margin: 100px auto; padding: 30px; background: #202c33; border-radius: 12px; border: 1px solid #2a3942; text-align: center; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='login-box'>", unsafe_allow_html=True)
    st.title("🔒 Allan AI")
    st.caption("Acesso Restrito ao Proprietário")
    
    input_pass = st.text_input("Senha de Acesso", type="password", key="login_input")
    if st.button("Entrar no Sistema", use_container_width=True, type="primary"):
        if input_pass == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
            
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ============================================================
# BASE DE DADOS MACIÇA DE LONGO PRAZO PRÉ-CARREGADA
# ============================================================

DEFAULT_PROFILE = [
    "IDENTIDADE: Allan Vitor Portello, 26 anos (Nascido em 21/04/2000). Altura: 1.90m, Peso: ~118.9kg.",
    "FAMÍLIA: Casado com Beatriz. Ela é formada em agronomia, cursa gestão de negócios e trabalha na A&W.",
    "LOCALIZAÇÃO E MORADIA: Atualmente em Hamilton, Ontario, porém concluindo o contrato de aluguel atual (setembro/2026) e em processo de mudança para Brantford.",
    "TRABALHO: Atua no setor de limpeza no Canadá e trabalha com o colega Serdar. O Allan não possui diploma universitário.",
    "METAS FINANCEIRAS E ESTUDOS: Planejando a estruturação de um plano de pagamento para a parcela de CAD .000 da universidade da Beatriz com vencimento para setembro/2026.",
    "VEÍCULO: Proprietário de um Mazda 3 (ano 2012). Objetivo de curto prazo: comprar um carro mais novo utilizando o Mazda 3 como entrada na negociação. Mantém o carro de forma rigorosa com polimentos e cuidados.",
    "GAMING & TECH: Joga FPS competitivo (Counter-Strike 2, Warzone) e tem profundo interesse na economia e valores do mercado de skins do CS2. Adora projetar, montar e otimizar computadores de alta performance e ajustar periféricos.",
    "FITNESS & DIETA: Pratica musculação focada em hipertrofia na Crunch Fitness. Mantém uma dieta pragmática hiperproteica baseada em peito de frango, carne moída magra e ovos.",
    "ESTILO DE COMUNICAÇÃO: Responda de forma extremamente lógica, racional e com foco em dados. Elimine clichês corporativos, introduções vazias e conclusões óbvias. Maximize a densidade da informação.",
    "MOEDA E REFERÊNCIA: Todas as análises financeiras e precificações devem ser em Dólar Canadense (CAD / $)."
]

def load_long_term_memory() -> dict:
    memory_data = {"user_facts": DEFAULT_PROFILE.copy(), "history": {}}
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                facts = list(set(DEFAULT_PROFILE + saved.get("user_facts", [])))
                return {"user_facts": facts, "history": saved.get("history", {})}
        except Exception:
            pass
    return memory_data

def save_long_term_memory(memory_data: dict) -> None:
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

if "long_memory" not in st.session_state:
    st.session_state.long_memory = load_long_term_memory()

# ============================================================
# AGENTES E ESTRUTURA
# ============================================================

AGENTS = {
    "orchestrator": {
        "name": "Allan AI Core",
        "icon": "🤖",
        "description": "Assistente central. Inteligência e triagem automatizada.",
        "language": "pt-BR",
        "system_prompt": "Você é o Allan AI Core. Acesso completo ao perfil do Allan. Responda com objetividade máxima e precisão técnica. Encaminhe demandas específicas."
    },
    "personal": {
        "name": "Personal Agent",
        "icon": "👤",
        "description": "Gestão de tempo, rotina diária e organização pessoal.",
        "language": "pt-BR",
        "system_prompt": "Você é o Personal Agent do Allan AI. Auxilie na mudança para Brantford, escalas de trabalho com Serdar e organização geral."
    },
    "finance": {
        "name": "Finance Agent",
        "icon": "💰",
        "description": "Análise financeira, orçamento e extratos em CAD ($).",
        "language": "pt-BR",
        "system_prompt": "Você é o Finance Agent do Allan AI. Foco no plano de CAD  da universidade da Beatriz e projeções para o trade-in do Mazda 3 2012."
    },
    "tech": {
        "name": "Tech Agent",
        "icon": "💻",
        "description": "Engenharia de software, PowerShell, Docker e Hardware.",
        "language": "pt-BR",
        "system_prompt": "Você é o Tech Agent do Allan AI. Entregue soluções exatas para programação, montagem de PCs, otimização de hardware e setups para CS2."
    },
    "coach": {
        "name": "Coach Agent",
        "icon": "🏋️",
        "description": "Treinos para hipertrofia e acompanhamento nutricional.",
        "language": "pt-BR",
        "system_prompt": "Você é o Coach Agent do Allan AI. Prescreva planos de treino hipertróficos (Crunch Fitness) e controle a dieta proteica baseada em carne moída, frango e ovos."
    },
    "business": {
        "name": "Business Agent",
        "icon": "💼",
        "description": "Estratégia comercial, precificação e mercado.",
        "language": "pt-BR",
        "system_prompt": "Você é o Business Agent do Allan AI. Analise a economia de itens de jogos (Skins CS2) e projetos de negócios em CAD ($)."
    },
    "english": {
        "name": "English Teacher",
        "icon": "🇺🇸",
        "description": "Professor de inglês: tradução, correções e pronúncia.",
        "language": "en-US",
        "system_prompt": "You are the English Teacher agent of Allan AI. Help Allan improve English using natural Canadian context (Ontario)."
    },
}

if "current_agent" not in st.session_state:
    st.session_state.current_agent = "orchestrator"

if "conversations" not in st.session_state:
    st.session_state.conversations = st.session_state.long_memory.get("history", {agent_id: [] for agent_id in AGENTS})

if "speech_text" not in st.session_state:
    st.session_state.speech_text = ""

if "speech_id" not in st.session_state:
    st.session_state.speech_id = 0

if "last_voice_message" not in st.session_state:
    st.session_state.last_voice_message = ""

st.markdown("""
<style>
:root {
    --amoled: #0b141a;
    --sidebar: #111b21;
    --bubble-ai: #202c33;
    --bubble-user: #005c4b;
    --border: #2a3942;
    --green: #00a884;
    --text: #e9edef;
    --muted: #8696a0;
}
.stApp, [data-testid="stAppViewContainer"] { background: var(--amoled) !important; color: var(--text) !important; }
[data-testid="stHeader"] { background: transparent !important; }
.main .block-container { max-width: 1400px; padding-top: 12px; padding-bottom: 100px; }
[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child { background: var(--sidebar) !important; border-right: 1px solid var(--border); }
[data-testid="stSidebar"] .stButton > button { min-height: 52px !important; width: 100% !important; border: 0 !important; border-left: 3px solid transparent !important; border-radius: 0 !important; background: transparent !important; color: var(--text) !important; text-align: left !important; padding: 10px 14px !important; font-size: 15px !important; }
[data-testid="stSidebar"] .stButton > button:hover { background: #202c33 !important; border-left-color: var(--green) !important; }

.chat-header { min-height: 64px; display: flex; align-items: center; gap: 12px; background: var(--bubble-ai); border: 1px solid var(--border); border-radius: 12px; padding: 10px 16px; margin-bottom: 12px; }
.chat-avatar { width: 42px; height: 42px; display: flex; align-items: center; justify-content: center; background: var(--sidebar); border-radius: 50%; font-size: 22px; }
.chat-agent-name { color: var(--text); font-size: 16px; font-weight: 600; }
.chat-agent-description { color: var(--muted); font-size: 12px; }

.chat-history { padding: 4px 2% 100px; }
.message-user { display: flex; justify-content: flex-end; margin: 8px 0; }
.message-ai { display: flex; justify-content: flex-start; margin: 8px 0; }
.bubble-user { max-width: 80%; background: var(--bubble-user); border: 1px solid #008069; border-radius: 10px 3px 10px 10px; padding: 10px 14px; font-size: 14px; }
.bubble-ai { max-width: 82%; background: var(--bubble-ai); border: 1px solid var(--border); border-radius: 3px 10px 10px 10px; padding: 10px 14px; font-size: 14px; }
.agent-label { color: var(--green); font-size: 11px; font-weight: 700; margin-bottom: 6px; }
.message-time { color: var(--muted); font-size: 9px; text-align: right; margin-top: 4px; }

.empty-chat { min-height: 50vh; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
.empty-chat-icon { font-size: 52px; margin-bottom: 10px; }
.empty-chat-title { color: var(--text); font-size: 22px; font-weight: 600; }
.empty-chat-description { color: var(--muted); max-width: 480px; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

def now_time() -> str: return time.strftime("%H:%M")
def get_history(agent_id: str) -> list[dict[str, Any]]: return st.session_state.conversations.get(agent_id, [])

def add_message(agent_id: str, role: str, content: str, agent: dict[str, Any] | None = None) -> None:
    if agent_id not in st.session_state.conversations:
        st.session_state.conversations[agent_id] = []
    st.session_state.conversations[agent_id].append({"role": role, "content": content, "time": now_time(), "agent": agent})
    st.session_state.long_memory["history"] = st.session_state.conversations
    save_long_term_memory(st.session_state.long_memory)

def clean_for_speech(text: str) -> str:
    text = re.sub(r"`.*?`", " ", text, flags=re.S)
    text = re.sub(r"([^]*)", r"\1", text)
    text = re.sub(r"[*_#>-]", " ", text)
    return text.strip()

def markdown_to_html(text: str) -> str:
    value = html.escape(text)
    value = re.sub(r"`(?:[\w+-]+)?\n?(.*?)`", r"<pre><code>\1</code></pre>", value, flags=re.S)
    value = re.sub(r"([^]+)", r"<code>\1</code>", value)
    value = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", value, flags=re.S)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", value)
    value = value.replace("\n", "<br>")
    return value

def ask_deepseek(agent_id: str, history: list[dict[str, Any]]) -> str:
    if "DEEPSEEK_API_KEY" not in st.secrets:
        raise RuntimeError("DEEPSEEK_API_KEY não configurada nos Secrets.")
    api_key = st.secrets["DEEPSEEK_API_KEY"]
    agent = AGENTS[agent_id]

    memory_facts = "\n- ".join(st.session_state.long_memory.get("user_facts", []))
    system_content = f"{agent['system_prompt'].strip()}\n\n[MEMÓRIA DE LONGO PRAZO DO USUÁRIO]:\n- {memory_facts}"

    messages = [{"role": "system", "content": system_content}]
    for item in history[-30:]:
        if item.get("role") in {"user", "assistant"} and item.get("content"):
            messages.append({"role": item["role"], "content": item["content"]})

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "deepseek-chat", "messages": messages, "temperature": 0.7}

    response = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=60)
    data = response.json()
    if not response.ok:
        raise RuntimeError(f"DeepSeek: {data.get('error', {}).get('message', 'Erro API')}")
    return data["choices"][0]["message"]["content"].strip()

COMPOSER_HTML = """
<div class="composer-root">
    <div id="composerStatus" class="composer-status"></div>
    <div class="composer-bar">
        <textarea id="composerInput" rows="1" placeholder="Digite uma mensagem..."></textarea>
        <button id="micButton" class="composer-button mic-button" type="button" title="Falar">🎙️</button>
        <button id="sendButton" class="composer-button send-button" type="button" title="Enviar">➤</button>
    </div>
</div>
"""

COMPOSER_CSS = """
.composer-root { width: 100%; font-family: -apple-system, sans-serif; }
.composer-bar { width: 100%; min-height: 50px; display: flex; align-items: center; gap: 8px; padding: 4px 8px 4px 16px; background: #202c33; border: 1px solid #2a3942; border-radius: 25px; }
#composerInput { flex: 1; border: 0; outline: 0; background: transparent; color: #e9edef; font-size: 14px; resize: none; max-height: 120px; }
.composer-button { width: 38px; height: 38px; border: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 16px; }
.mic-button { background: #111b21; color: #8696a0; border: 1px solid #2a3942; }
.mic-button.listening { background: #005c4b; color: #fff; border-color: #00a884; }
.send-button { background: #00a884; color: #fff; }
.composer-status { font-size: 10px; color: #8696a0; padding-left: 16px; height: 14px; }
"""

COMPOSER_JS = r"""
export default function(component) {
    const { parentElement, data, setTriggerValue } = component;
    if (!parentElement) return;

    const input = parentElement.querySelector("#composerInput");
    const micButton = parentElement.querySelector("#micButton");
    const sendButton = parentElement.querySelector("#sendButton");
    const status = parentElement.querySelector("#composerStatus");

    if (!input || !micButton || !sendButton) return;

    let recognition = null;
    let listening = false;

    const speechText = data?.speech_text || "";
    const speechId = data?.speech_id ?? 0;
    if (speechText && speechId !== window.__lastSpeechId) {
        window.__lastSpeechId = speechId;
        if ("speechSynthesis" in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(speechText);
            utterance.lang = data?.speech_language || "pt-BR";
            window.speechSynthesis.speak(utterance);
        }
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) { micButton.style.display = "none"; return; }

    recognition = new SpeechRecognition();
    recognition.lang = data?.input_language || "pt-BR";
    recognition.continuous = false;

    recognition.onresult = (e) => {
        const text = e.results[0][0].transcript;
        input.value = text;
        setTriggerValue("voice_message", text);
    };

    recognition.onstart = () => {
        listening = true;
        micButton.classList.add("listening");
        if (status) status.textContent = "Ouvindo...";
    };

    recognition.onend = () => {
        listening = false;
        micButton.classList.remove("listening");
        if (status) status.textContent = "";
    };

    micButton.onclick = () => {
        if (listening) recognition.stop();
        else {
            try { recognition.lang = data?.input_language || "pt-BR"; recognition.start(); } catch(e) {}
        }
    };

    const send = () => {
        const text = input.value.trim();
        if (!text) return;
        setTriggerValue("message", text);
        input.value = "";
    };

    sendButton.onclick = send;
    input.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };
}
"""

composer_component = components.component(name="allan_ai_composer", html=COMPOSER_HTML, css=COMPOSER_CSS, js=COMPOSER_JS)

with st.sidebar:
    st.markdown('<div style="font-size:20px; font-weight:bold; color:#e9edef; padding:8px 0;">Allan AI</div><div style="font-size:11px; color:#8696a0; margin-bottom:12px;">Conversas ativas</div>', unsafe_allow_html=True)
    for a_id, a_data in AGENTS.items():
        sel = (st.session_state.current_agent == a_id)
        lbl = f"{a_data['icon']} {a_data['name']}"
        if st.button(lbl, key=f"agent_{a_id}", use_container_width=True, type="primary" if sel else "secondary"):
            if not sel:
                st.session_state.current_agent = a_id
                st.rerun()

    st.markdown("---")
    if st.button("🔒 Sair do Sistema", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

agent_id = st.session_state.current_agent
agent = AGENTS[agent_id]

st.markdown(f'<div class="chat-header"><div class="chat-avatar">{agent["icon"]}</div><div><div class="chat-agent-name">{html.escape(agent["name"])}</div><div class="chat-agent-description">{html.escape(agent["description"])}</div></div></div>', unsafe_allow_html=True)

history = get_history(agent_id)
if not history:
    st.markdown(f'<div class="empty-chat"><div class="empty-chat-icon">{agent["icon"]}</div><div class="empty-chat-title">{html.escape(agent["name"])}</div><div class="empty-chat-description">{html.escape(agent["description"])}</div></div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="chat-history">', unsafe_allow_html=True)
    for msg in history:
        r = msg["role"]
        c = markdown_to_html(msg["content"])
        t = html.escape(msg.get("time", ""))
        if r == "user":
            st.markdown(f'<div class="message-user"><div class="bubble-user">{c}<div class="message-time">{t}</div></div></div>', unsafe_allow_html=True)
        else:
            lbl = html.escape(msg.get("agent", {}).get("name", "Allan AI"))
            st.markdown(f'<div class="message-ai"><div class="bubble-ai"><div class="agent-label">{msg.get("agent", {}).get("icon", "🤖")} {lbl}</div>{c}<div class="message-time">{t}</div></div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

composer_result = composer_component(
    key="allan_ai_composer_instance",
    data={"input_language": agent["language"], "speech_language": agent["language"], "speech_text": st.session_state.speech_text, "speech_id": st.session_state.speech_id},
    on_message_change=lambda: None,
    on_voice_message_change=lambda: None,
)

def process_user_message(text: str) -> None:
    text = text.strip()
    if not text: return
    add_message(agent_id, "user", text)
    try:
        with st.spinner(f"{agent['name']} está pensando..."):
            answer = ask_deepseek(agent_id, get_history(agent_id))
        add_message(agent_id, "assistant", answer, agent)
        st.session_state.speech_text = clean_for_speech(answer)
        st.session_state.speech_id += 1
    except Exception as error:
        add_message(agent_id, "assistant", f"**Erro:** {error}", {"name": "Allan AI", "icon": "⚠️"})

msg_trig = getattr(composer_result, "message", None)
voice_trig = getattr(composer_result, "voice_message", None)

if voice_trig:
    v_text = str(voice_trig).strip()
    if v_text and v_text != st.session_state.last_voice_message:
        st.session_state.last_voice_message = v_text
        process_user_message(v_text)
        st.rerun()
elif msg_trig:
    m_text = str(msg_trig).strip()
    if m_text:
        process_user_message(m_text)
        st.rerun()