import html
import re
import time
from typing import Any

import requests
import streamlit as st
import streamlit.components.v2 as components

st.set_page_config(
    page_title="Allan AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

AGENTS = {
    "orchestrator": {
        "icon": "🤖",
        "name": "Orquestrador",
        "short_name": "Auto",
        "description": "Coordena os agentes e decide como executar cada tarefa.",
        "language": "pt-BR",
        "system_prompt": """Você é o Orquestrador central do Allan AI. Moeda padrão: Dólar Canadense (CAD / $). Cidade: Hamilton, Ontario. Compreenda a solicitação do usuário e decida a melhor forma de atendê-la com clareza e objetividade."""
    },
    "personal": {
        "icon": "👤",
        "name": "Personal Agent",
        "short_name": "Personal",
        "description": "Organização pessoal, planejamento, produtividade e rotina.",
        "language": "pt-BR",
        "system_prompt": """Você é o Personal Agent do Allan AI. Especialista em gestão de tempo, produtividade e organização pessoal em Hamilton/Ontario."""
    },
    "finance": {
        "icon": "💰",
        "name": "Finance Agent",
        "short_name": "Finance",
        "description": "Finanças pessoais, orçamento e análise em CAD $.",
        "language": "pt-BR",
        "system_prompt": """Você é o Finance Agent do Allan AI. Mantenha todas as análises estritamente em Dólar Canadense (CAD / $). Estrutura: Tabela de Lançamentos | Totais | Saldo Final Líquido."""
    },
    "tech": {
        "icon": "💻",
        "name": "Tech Agent",
        "short_name": "Tech",
        "description": "Python, APIs, Docker, IA e engenharia de software.",
        "language": "pt-BR",
        "system_prompt": """Você é o Tech Agent do Allan AI. Entregue códigos limpos em PowerShell, automações e comandos Docker prontos para uso."""
    },
    "coach": {
        "icon": "🏋️",
        "name": "Coach Agent",
        "short_name": "Coach",
        "description": "Metas, hábitos, disciplina e acompanhamento de progresso.",
        "language": "pt-BR",
        "system_prompt": """Você é o Coach Agent do Allan AI. Prescreva planos de treino focados em hipertrofia (RIR/RPE) e dietas de alta proteína em g/kg."""
    },
    "business": {
        "icon": "💼",
        "name": "Business Agent",
        "short_name": "Business",
        "description": "Negócios, estratégia, produtos e análise em CAD $.",
        "language": "pt-BR",
        "system_prompt": """Você é o Business Agent do Allan AI. Calcule taxa por hora, custos operacionais e margens de lucro para serviços comerciais em Dólar Canadense (CAD / $)."""
    },
    "english": {
        "icon": "🇺🇸",
        "name": "English Teacher",
        "short_name": "English",
        "description": "Conversação, gramática, vocabulário e pronúncia.",
        "language": "en-US",
        "system_prompt": """You are the English Teacher agent of Allan AI. Traduza mantendo o contexto canadense natural, corrija erros gramaticais e ofereça explicações simples."""
    },
}

st.markdown("""
<style>
:root {
    --bg: #0b141a;
    --sidebar: #111b21;
    --panel: #202c33;
    --panel-hover: #2a3942;
    --green: #00a884;
    --user: #005c4b;
    --user-border: #008069;
    --text: #e9edef;
    --muted: #8696a0;
    --border: #2a3942;
}
.stApp, [data-testid="stAppViewContainer"] { background: var(--bg) !important; color: var(--text) !important; }
[data-testid="stHeader"] { background: transparent !important; }
.main .block-container { max-width: 1200px; padding-top: 1rem; padding-bottom: 2rem; }
[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child { background: var(--sidebar) !important; }
.chat-header { display: flex; align-items: center; gap: 12px; background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 12px 16px; margin-bottom: 12px; }
.chat-avatar { width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; background: var(--sidebar); border-radius: 50%; font-size: 22px; }
.message-user { display: flex; justify-content: flex-end; margin: 8px 0; }
.message-ai { display: flex; justify-content: flex-start; margin: 8px 0; }
.bubble-user { max-width: 80%; background: var(--user); border: 1px solid var(--user-border); border-radius: 10px 3px 10px 10px; padding: 10px 14px; color: var(--text); }
.bubble-ai { max-width: 82%; background: var(--panel); border: 1px solid var(--border); border-radius: 3px 10px 10px 10px; padding: 10px 14px; color: var(--text); }
.agent-label { color: var(--green); font-size: 11px; font-weight: 700; margin-bottom: 4px; }
.message-time { color: var(--muted); font-size: 9px; text-align: right; margin-top: 4px; }
[data-testid="stChatInput"] { background: var(--panel) !important; border: 1px solid var(--border) !important; border-radius: 24px !important; }
[data-testid="stChatInput"] textarea { color: var(--text) !important; }
</style>
""", unsafe_allow_html=True)

if "current_agent" not in st.session_state:
    st.session_state.current_agent = "orchestrator"

if "conversations" not in st.session_state:
    st.session_state.conversations = {agent_id: [] for agent_id in AGENTS}

if "speech_request_id" not in st.session_state:
    st.session_state.speech_request_id = 0

if "speech_text" not in st.session_state:
    st.session_state.speech_text = ""

def clean_for_speech(text: str) -> str:
    text = re.sub(r"`.*?`", " ", text, flags=re.S)
    text = re.sub(r"([^]*)", r"\1", text)
    text = re.sub(r"[*_#>-]", " ", text)
    return text.strip()

def add_message(agent_id: str, role: str, content: str, agent: dict[str, Any] | None = None) -> None:
    st.session_state.conversations[agent_id].append({
        "role": role,
        "content": content,
        "time": time.strftime("%H:%M"),
        "agent": agent,
    })

def get_history(agent_id: str) -> list[dict[str, Any]]:
    return st.session_state.conversations.get(agent_id, [])

def ask_deepseek(agent_id: str, history: list[dict[str, Any]]) -> str:
    if "DEEPSEEK_API_KEY" not in st.secrets:
        raise RuntimeError("DEEPSEEK_API_KEY não foi encontrada nos Secrets do Streamlit Cloud.")

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

VOICE_HTML = """
<div class="voice-wrapper" style="display:flex; align-items:center; gap:10px;">
    <button id="voiceButton" style="width:40px; height:40px; border-radius:50%; background:#202c33; border:1px solid #2a3942; color:#e9edef; font-size:18px; cursor:pointer;">🎙️</button>
    <div id="voiceStatus" style="color:#8696a0; font-size:12px;">Clique no microfone para falar</div>
    <div id="voiceTranscript" style="color:#e9edef; font-size:12px; font-weight:bold;"></div>
</div>
"""

VOICE_CSS = ""

VOICE_JS = r"""
export default function(component) {
    const { parentElement, setTriggerValue, data } = component;
    if (!parentElement) return;

    const button = parentElement.querySelector("#voiceButton");
    const status = parentElement.querySelector("#voiceStatus");
    const transcript = parentElement.querySelector("#voiceTranscript");

    if (button) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            if (status) status.textContent = "Microfone não suportado no navegador.";
        } else {
            const recognition = new SpeechRecognition();
            recognition.lang = data?.input_lang || "pt-BR";
            recognition.continuous = false;

            button.onclick = () => {
                try {
                    recognition.lang = data?.input_lang || "pt-BR";
                    recognition.start();
                    if (status) status.textContent = "Ouvindo...";
                    button.style.background = "#005c4b";
                } catch (e) {
                    recognition.stop();
                }
            };

            recognition.onresult = (e) => {
                const text = e.results[0][0].transcript;
                if (transcript) transcript.textContent = text;
                setTriggerValue("voice_message", text);
            };

            recognition.onend = () => {
                if (status) status.textContent = "Clique no microfone para falar";
                button.style.background = "#202c33";
            };
        }
    }

    // Text to Speech Output seguro sem dependencia de dataset
    const speechText = data?.speech_text ?? "";
    const speechId = data?.speech_id ?? 0;
    
    if (!window.__lastSpeechId) window.__lastSpeechId = 0;

    if (speechText && speechId !== window.__lastSpeechId) {
        window.__lastSpeechId = speechId;
        if ("speechSynthesis" in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(speechText);
            utterance.lang = data?.speech_lang || "pt-BR";
            window.speechSynthesis.speak(utterance);
        }
    }
}
"""

voice_component = components.component(
    name="allan_ai_voice",
    html=VOICE_HTML,
    css=VOICE_CSS,
    js=VOICE_JS,
)

with st.sidebar:
    st.markdown("### 💬 Allan AI")
    st.caption("Conversas ativas:")
    for a_id, a_data in AGENTS.items():
        if st.button(f"{a_data['icon']} {a_data['name']}", key=f"btn_{a_id}", use_container_width=True):
            st.session_state.current_agent = a_id
            st.rerun()

agent_id = st.session_state.current_agent
agent = AGENTS[agent_id]

st.markdown(f"""
    <div class="chat-header">
        <div class="chat-avatar">{agent['icon']}</div>
        <div>
            <div style="font-weight:bold; color:#e9edef;">{agent['name']}</div>
            <div style="font-size:12px; color:#8696a0;">{agent['description']}</div>
        </div>
    </div>
""", unsafe_allow_html=True)

voice_result = voice_component(
    data={
        "input_lang": agent["language"],
        "speech_text": st.session_state.speech_text,
        "speech_lang": agent["language"],
        "speech_id": st.session_state.speech_request_id,
    },
    key="voice_comp",
    height=50,
)

voice_message = getattr(voice_result, "voice_message", None)
if voice_message and voice_message != st.session_state.get("last_voice_msg"):
    st.session_state.last_voice_msg = voice_message
    add_message(agent_id, "user", voice_message)
    try:
        with st.spinner("Pensando..."):
            ans = ask_deepseek(agent_id, get_history(agent_id))
        add_message(agent_id, "assistant", ans, agent)
        st.session_state.speech_text = clean_for_speech(ans)
        st.session_state.speech_request_id += 1
    except Exception as err:
        add_message(agent_id, "assistant", f"**Erro:** {err}", {"icon": "⚠️", "name": "Allan AI"})
    st.rerun()

history = get_history(agent_id)
for msg in history:
    role = msg["role"]
    if role == "user":
        st.markdown(f'<div class="message-user"><div class="bubble-user">{html.escape(msg["content"])}<div class="message-time">{msg["time"]}</div></div></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="message-ai"><div class="bubble-ai"><div class="agent-label">{msg.get("agent", {}).get("icon", "🤖")} {msg.get("agent", {}).get("name", "Allan AI")}</div>{html.escape(msg["content"])}<div class="message-time">{msg["time"]}</div></div></div>', unsafe_allow_html=True)

if prompt := st.chat_input(f"Mensagem para {agent['name']}..."):
    add_message(agent_id, "user", prompt)
    try:
        with st.spinner("Pensando..."):
            ans = ask_deepseek(agent_id, get_history(agent_id))
        add_message(agent_id, "assistant", ans, agent)
        st.session_state.speech_text = clean_for_speech(ans)
        st.session_state.speech_request_id += 1
    except Exception as err:
        add_message(agent_id, "assistant", f"**Erro:** {err}", {"icon": "⚠️", "name": "Allan AI"})
    st.rerun()