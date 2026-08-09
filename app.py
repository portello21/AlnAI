import html
import re
import time
from typing import Any

import requests
import streamlit as st
import streamlit.components.v2 as components

st.set_page_config(
    page_title="Allan AI",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

AGENTS = {
    "orchestrator": {
        "name": "Orquestrador",
        "short_name": "Auto",
        "description": "Coordena agentes e decide como executar cada tarefa.",
        "language": "pt-BR",
        "avatar": """<div class="avatar avatar-orchestrator"><svg viewBox="0 0 64 64"><rect x="13" y="16" width="38" height="31" rx="10"/><circle cx="25" cy="31" r="4"/><circle cx="39" cy="31" r="4"/><path d="M24 40 Q32 45 40 40"/><path d="M32 16 V9"/><circle cx="32" cy="7" r="3"/></svg></div>""",
        "system_prompt": """Você é o Orquestrador central do Allan AI. Moeda padrão: Dólar Canadense (CAD / $). Cidade: Hamilton, Ontario. Compreenda a solicitação do usuário e decida a melhor forma de atendê-la."""
    },
    "personal": {
        "name": "Personal Agent",
        "short_name": "Personal",
        "description": "Organização pessoal, planejamento e produtividade.",
        "language": "pt-BR",
        "avatar": """<div class="avatar avatar-personal"><svg viewBox="0 0 64 64"><circle cx="32" cy="22" r="11"/><path d="M14 54 Q16 38 32 38 Q48 38 50 54"/><path d="M21 13 Q32 5 43 13"/><path d="M24 23 H40"/></svg></div>""",
        "system_prompt": """Você é o Personal Agent do Allan AI. Especialidade em gestão de tempo, produtividade e organização pessoal em Hamilton/Ontario."""
    },
    "finance": {
        "name": "Finance Agent",
        "short_name": "Finance",
        "description": "Finanças pessoais, orçamento e análises em CAD $.",
        "language": "pt-BR",
        "avatar": """<div class="avatar avatar-finance"><svg viewBox="0 0 64 64"><rect x="13" y="17" width="38" height="32" rx="7"/><path d="M18 25 H46"/><path d="M22 34 H30"/><path d="M22 41 H38"/><circle cx="43" cy="39" r="4"/></svg></div>""",
        "system_prompt": """Você é o Finance Agent do Allan AI. Mantenha análises estritamente em Dólar Canadense (CAD / $). Estrutura: Lançamentos | Totais | Saldo Final Líquido."""
    },
    "tech": {
        "name": "Tech Agent",
        "short_name": "Tech",
        "description": "Python, APIs, Docker, IA e engenharia de software.",
        "language": "pt-BR",
        "avatar": """<div class="avatar avatar-tech"><svg viewBox="0 0 64 64"><rect x="10" y="13" width="44" height="35" rx="5"/><path d="M18 22 L25 28 L18 34"/><path d="M29 35 H43"/><path d="M10 43 H54"/><circle cx="19" cy="18" r="1.8"/><circle cx="26" cy="18" r="1.8"/><circle cx="33" cy="18" r="1.8"/></svg></div>""",
        "system_prompt": """Você é o Tech Agent do Allan AI. Engenheiro de Software Full-Stack sênior. Entregue soluções técnicas exatas, scripts PowerShell e comandos Docker."""
    },
    "coach": {
        "name": "Coach Agent",
        "short_name": "Coach",
        "description": "Metas, hábitos, disciplina e progresso.",
        "language": "pt-BR",
        "avatar": """<div class="avatar avatar-coach"><svg viewBox="0 0 64 64"><circle cx="32" cy="18" r="7"/><path d="M25 27 L19 43"/><path d="M39 27 L45 43"/><path d="M25 29 L39 29"/><path d="M24 44 L18 54"/><path d="M40 44 L46 54"/><path d="M14 31 H50"/><path d="M10 27 V35"/><path d="M54 27 V35"/></svg></div>""",
        "system_prompt": """Você é o Coach Agent do Allan AI. Prescreva planos de treino focados em hipertrofia (RIR/RPE) e dietas hiperproteicas."""
    },
    "business": {
        "name": "Business Agent",
        "short_name": "Business",
        "description": "Negócios, estratégia, produtos e mercado em CAD $.",
        "language": "pt-BR",
        "avatar": """<div class="avatar avatar-business"><svg viewBox="0 0 64 64"><rect x="12" y="19" width="40" height="32" rx="5"/><path d="M25 19 V13 H39 V19"/><path d="M12 29 H52"/><path d="M29 29 V35 H35 V29"/><path d="M21 43 H43"/></svg></div>""",
        "system_prompt": """Você é o Business Agent do Allan AI. Calcule taxas operacionais e margens de lucro em Dólar Canadense (CAD / $)."""
    },
    "english": {
        "name": "English Teacher",
        "short_name": "English",
        "description": "Conversação, gramática, vocabulário e pronúncia.",
        "language": "en-US",
        "avatar": """<div class="avatar avatar-english"><svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="22"/><path d="M21 28 Q32 19 43 28"/><circle cx="25" cy="32" r="3"/><circle cx="39" cy="32" r="3"/><path d="M24 42 Q32 48 40 42"/><path d="M17 18 L22 13"/><path d="M47 18 L42 13"/></svg></div>""",
        "system_prompt": """You are the English Teacher agent of Allan AI. Help improve English using natural Canadian expressions, corrections, and clear explanations."""
    },
}

if "current_agent" not in st.session_state:
    st.session_state.current_agent = "orchestrator"

if "conversations" not in st.session_state:
    st.session_state.conversations = {agent_id: [] for agent_id in AGENTS}

if "speech_text" not in st.session_state:
    st.session_state.speech_text = ""

if "speech_language" not in st.session_state:
    st.session_state.speech_language = "pt-BR"

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
    --green-dark: #008069;
    --text: #e9edef;
    --muted: #8696a0;
}
.stApp, [data-testid="stAppViewContainer"] { background: var(--amoled) !important; color: var(--text) !important; }
[data-testid="stHeader"] { background: transparent !important; }
.main .block-container { max-width: 1500px; padding-top: 12px; padding-bottom: 100px; }
[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child { background: var(--sidebar) !important; border-right: 1px solid var(--border); }
.sidebar-brand { padding: 8px 8px 22px 8px; }
.sidebar-brand-title { color: var(--text); font-size: 22px; font-weight: 700; }
.sidebar-brand-subtitle { color: var(--muted); font-size: 12px; margin-top: 3px; }
.sidebar-section { color: var(--muted); font-size: 10px; font-weight: 700; letter-spacing: 1.2px; padding: 0 8px 7px; }
[data-testid="stSidebar"] .stButton > button { min-height: 58px !important; width: 100% !important; border: 0 !important; border-left: 3px solid transparent !important; border-radius: 0 !important; background: transparent !important; color: var(--text) !important; text-align: left !important; padding: 7px 9px !important; }
[data-testid="stSidebar"] .stButton > button:hover { background: #202c33 !important; border-left-color: var(--green) !important; }

.avatar { width: 43px; height: 43px; flex: 0 0 43px; display: flex; align-items: center; justify-content: center; border-radius: 50%; background: #202c33; border: 1px solid #34454d; overflow: hidden; }
.avatar svg { width: 27px; height: 27px; fill: none; stroke: currentColor; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }
.avatar-orchestrator { color: #56d6bb; background: #12342f; }
.avatar-personal { color: #7eb7ff; background: #182c45; }
.avatar-finance { color: #6de0b1; background: #15372d; }
.avatar-tech { color: #8ea9ff; background: #1b2340; }
.avatar-coach { color: #ffb86b; background: #3a2918; }
.avatar-business { color: #b9a1ff; background: #2a2040; }
.avatar-english { color: #7fd8ff; background: #153442; }

.chat-header { min-height: 68px; display: flex; align-items: center; gap: 12px; background: var(--bubble-ai); border: 1px solid var(--border); border-radius: 12px; padding: 10px 15px; margin-bottom: 12px; }
.chat-agent-name { color: var(--text); font-size: 16px; font-weight: 600; }
.chat-agent-description { color: var(--muted); font-size: 12px; margin-top: 2px; }
.online { margin-left: auto; color: var(--green); font-size: 11px; }

.chat-history { padding: 4px 3% 120px; }
.message-user { display: flex; justify-content: flex-end; margin: 7px 0; }
.message-ai { display: flex; justify-content: flex-start; margin: 7px 0; }
.bubble-user { max-width: 78%; background: var(--bubble-user); border: 1px solid var(--green-dark); border-radius: 10px 3px 10px 10px; padding: 10px 13px; font-size: 14px; }
.bubble-ai { max-width: 82%; background: var(--bubble-ai); border: 1px solid var(--border); border-radius: 3px 10px 10px 10px; padding: 10px 13px; font-size: 14px; }
.agent-label { color: var(--green); font-size: 11px; font-weight: 700; margin-bottom: 7px; }
.message-time { color: var(--muted); font-size: 9px; text-align: right; margin-top: 6px; }

.empty-chat { min-height: 55vh; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
.empty-chat .avatar { width: 72px; height: 72px; margin-bottom: 15px; }
.empty-chat .avatar svg { width: 43px; height: 43px; }
.empty-chat-title { color: var(--text); font-size: 24px; font-weight: 600; }
.empty-chat-description { color: var(--muted); max-width: 500px; font-size: 14px; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

def now_time() -> str: return time.strftime("%H:%M")
def get_history(agent_id: str) -> list[dict[str, Any]]: return st.session_state.conversations[agent_id]
def add_message(agent_id: str, role: str, content: str, agent: dict[str, Any] | None = None) -> None:
    st.session_state.conversations[agent_id].append({"role": role, "content": content, "time": now_time(), "agent": agent})

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
        raise RuntimeError("DEEPSEEK_API_KEY não está configurada nos Secrets do Streamlit Cloud.")
    api_key = st.secrets["DEEPSEEK_API_KEY"]
    agent = AGENTS[agent_id]

    messages = [{"role": "system", "content": agent["system_prompt"].strip()}]
    for item in history[-30:]:
        if item.get("role") in {"user", "assistant"} and item.get("content"):
            messages.append({"role": item["role"], "content": item["content"]})

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "deepseek-chat", "messages": messages, "temperature": 0.7}

    response = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=60)
    data = response.json()
    if not response.ok:
        raise RuntimeError(f"DeepSeek: {data.get('error', {}).get('message', 'Erro na API')}")
    return data["choices"][0]["message"]["content"].strip()

COMPOSER_HTML = """
<div class="composer-root">
    <div id="composerStatus" class="composer-status"></div>
    <div class="composer-bar">
        <textarea id="composerInput" rows="1" maxlength="12000" placeholder="Digite uma mensagem..."></textarea>
        <button id="micButton" class="composer-button mic-button" type="button" title="Falar"><span id="micIcon">⌕</span></button>
        <button id="sendButton" class="composer-button send-button" type="button" title="Enviar"><span>➤</span></button>
    </div>
    <div id="liveTranscript" class="live-transcript"></div>
</div>
"""

COMPOSER_CSS = """
.composer-root { width: 100%; padding: 4px 0 8px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.composer-bar { width: 100%; min-height: 52px; display: flex; align-items: flex-end; gap: 7px; padding: 5px 6px 5px 15px; background: #202c33; border: 1px solid #2a3942; border-radius: 27px; }
#composerInput { flex: 1; width: 100%; min-height: 40px; max-height: 130px; resize: none; border: 0; outline: 0; background: transparent; color: #e9edef; font-size: 14px; padding: 10px 2px 7px; }
.composer-button { width: 40px; height: 40px; flex: 0 0 40px; border: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.mic-button { background: #111b21; color: #c8d2d7; border: 1px solid #2a3942; }
.mic-button.listening { background: #005c4b; color: #ffffff; border-color: #00a884; }
.send-button { background: #00a884; color: white; font-size: 17px; }
.composer-status { height: 17px; padding-left: 17px; color: #8696a0; font-size: 10px; opacity: 0; }
.composer-status.visible { opacity: 1; }
.live-transcript { position: absolute; max-width: 70%; margin-top: -30px; margin-left: 62px; color: #a9b6bb; font-size: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
"""

COMPOSER_JS = r"""
export default function(component) {
    const { parentElement, data, setTriggerValue, setStateValue } = component;
    if (!parentElement) return;

    const input = parentElement.querySelector("#composerInput");
    const micButton = parentElement.querySelector("#micButton");
    const sendButton = parentElement.querySelector("#sendButton");
    const micIcon = parentElement.querySelector("#micIcon");
    const status = parentElement.querySelector("#composerStatus");
    const transcript = parentElement.querySelector("#liveTranscript");

    if (!input || !micButton || !sendButton || !micIcon || !status || !transcript) return;

    let recognition = null;
    let listening = false;
    let finalText = "";
    let interimText = "";

    const speechText = data?.speech_text || "";
    const speechLanguage = data?.speech_language || "pt-BR";
    const speechId = data?.speech_id ?? 0;
    const globalLastSpeechId = window.__lastSpeechId;

    if (speechText && String(speechId) !== String(globalLastSpeechId ?? "")) {
        window.__lastSpeechId = speechId;
        if ("speechSynthesis" in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(speechText);
            utterance.lang = speechLanguage;
            window.speechSynthesis.speak(utterance);
        }
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        micButton.disabled = true;
        return;
    }

    recognition = new SpeechRecognition();
    recognition.lang = data?.input_language || "pt-BR";
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event) => {
        interimText = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const res = event.results[i];
            const text = res?.[0]?.transcript || "";
            if (res.isFinal) finalText += text + " ";
            else interimText += text;
        }
        transcript.textContent = (finalText + " " + interimText).trim();
    };

    recognition.onstart = () => {
        listening = true;
        finalText = ""; interimText = "";
        micButton.classList.add("listening");
        micIcon.textContent = "■";
        status.textContent = "Ouvindo...";
        status.classList.add("visible");
    };

    recognition.onend = () => {
        listening = false;
        micButton.classList.remove("listening");
        micIcon.textContent = "⌕";
        const text = finalText.trim();
        if (text) {
            input.value = text;
            setTriggerValue("voice_message", text);
        }
        status.classList.remove("visible");
    };

    micButton.onclick = () => {
        if (listening) recognition.stop();
        else {
            try { recognition.lang = data?.input_language || "pt-BR"; recognition.start(); }
            catch(e) {}
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
    st.markdown('<div class="sidebar-brand"><div class="sidebar-brand-title">Allan AI</div><div class="sidebar-brand-subtitle">Conversas ativas</div></div><div class="sidebar-section">AGENTES</div>', unsafe_allow_html=True)
    for a_id, a_data in AGENTS.items():
        sel = (st.session_state.current_agent == a_id)
        lbl = a_data["name"] + (" · Auto" if a_id == "orchestrator" else "")
        if st.button(lbl, key=f"agent_{a_id}", use_container_width=True, type="primary" if sel else "secondary"):
            if not sel:
                st.session_state.current_agent = a_id
                st.rerun()

agent_id = st.session_state.current_agent
agent = AGENTS[agent_id]

st.markdown(f'<div class="chat-header">{agent["avatar"]}<div><div class="chat-agent-name">{html.escape(agent["name"])}</div><div class="chat-agent-description">{html.escape(agent["description"])}</div></div><div class="online">● online</div></div>', unsafe_allow_html=True)

history = get_history(agent_id)
if not history:
    st.markdown(f'<div class="empty-chat">{agent["avatar"]}<div class="empty-chat-title">{html.escape(agent["name"])}</div><div class="empty-chat-description">{html.escape(agent["description"])}<br><br>Digite uma mensagem ou use o microfone integrado abaixo.</div></div>', unsafe_allow_html=True)
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
            st.markdown(f'<div class="message-ai"><div class="bubble-ai"><div class="agent-label">{lbl}</div>{c}<div class="message-time">{t}</div></div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

composer_result = composer_component(
    key="allan_ai_composer_instance",
    data={"input_language": "pt-BR", "speech_language": agent["language"], "speech_text": st.session_state.speech_text, "speech_id": st.session_state.speech_id},
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
        st.session_state.speech_language = agent["language"]
        st.session_state.speech_id += 1
    except Exception as error:
        add_message(agent_id, "assistant", f"**Erro:** {error}", {"name": "Allan AI"})

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