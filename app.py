import html
import json
import os
import re
import time
from typing import Any
import base64

import requests
import streamlit as st
import streamlit.components.v2 as components
from duckduckgo_search import DDGS

st.set_page_config(page_title="Allan AI - Multi-Profile", page_icon="🔒", layout="wide", initial_sidebar_state="expanded")

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
MEMORY_FILE = "long_term_memory.json"

PASSWORDS = {
    "Allan": st.secrets.get("ALLAN_PASSWORD", "Allan2026@Pass"),
    "Beatriz": st.secrets.get("BEATRIZ_PASSWORD", "Beatriz2026@Pass")
}

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "current_profile" not in st.session_state: st.session_state.current_profile = None

if not st.session_state.authenticated:
    st.markdown("<style>.stApp { background-color: #0b141a !important; color: #e9edef !important; } .login-box { max-width: 400px; margin: 100px auto; padding: 30px; background: #202c33; border-radius: 12px; border: 1px solid #2a3942; text-align: center; }</style>", unsafe_allow_html=True)
    st.markdown("<div class='login-box'>", unsafe_allow_html=True)
    st.title("🔒 Allan AI")
    profile_choice = st.selectbox("Perfil", ["Allan", "Beatriz"])
    input_pass = st.text_input("Senha", type="password")
    
    if st.button("Entrar", use_container_width=True, type="primary"):
        if input_pass == PASSWORDS[profile_choice]:
            st.session_state.authenticated = True
            st.session_state.current_profile = profile_choice
            st.rerun()
        else:
            st.error("Falha de autenticação.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

PROFILES = {
    "Allan": [
        "IDENTIDADE: Allan Vitor Portello, 26 anos (21/04/2000). Altura: 1.90m, Peso: ~118.9kg.",
        "FAMÍLIA: Casado com Beatriz (agronomia/A&W).",
        "LOCALIZAÇÃO: Hamilton, Ontario (mudando para Brantford em set/2026).",
        "TRABALHO: Setor de limpeza no Canadá com colega Serdar. Sem diploma universitário.",
        "METAS: Plano de CAD .000 (faculdade da Beatriz) para set/2026. Troca do Mazda 3 (2012) por carro novo.",
        "TECH & GAMES: Joga CS2 competitivo. Otimiza/monta PCs de alta performance.",
        "FITNESS: Musculação na Crunch Fitness. Dieta hiperproteica (ovos, frango, carne moída).",
        "ESTILO: Racional, lógico, sem clichês. Respostas densas e objetivas.",
        "MOEDA: Dólar Canadense (CAD / $)."
    ],
    "Beatriz": [
        "IDENTIDADE: Beatriz. Casada com Allan Vitor Portello.",
        "ESTUDOS E TRABALHO: Formada em agronomia, estudante de gestão de negócios. Trabalha na A&W.",
        "LOCALIZAÇÃO: Hamilton, Ontario (mudando para Brantford em set/2026).",
        "METAS FINANCEIRAS: Organizar parcelamento universitário de CAD .000 para setembro/2026.",
        "FITNESS & DIETA: Busca suporte de treino e dieta alinhados à rotina.",
        "ESTILO: Respostas práticas, encorajadoras e focadas em organização.",
        "MOEDA: Dólar Canadense (CAD / $)."
    ]
}

def load_long_term_memory() -> dict:
    base = {"Allan": {"user_facts": PROFILES["Allan"].copy(), "history": {}}, "Beatriz": {"user_facts": PROFILES["Beatriz"].copy(), "history": {}}}
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for p in ["Allan", "Beatriz"]:
                if p in saved:
                    base[p]["history"] = saved[p].get("history", {})
                    base[p]["user_facts"] = list(set(PROFILES[p] + saved[p].get("user_facts", [])))
        except Exception: pass
    return base

def save_long_term_memory(memory_data: dict) -> None:
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f: json.dump(memory_data, f, ensure_ascii=False, indent=2)
    except Exception: pass

if "long_memory" not in st.session_state: st.session_state.long_memory = load_long_term_memory()

AGENTS = {
    "orchestrator": {"name": "Allan AI Core", "icon": "🤖", "description": "Inteligência central e triagem.", "language": "pt-BR", "system_prompt": "Você é o Allan AI Core. Diretrizes estritas: 1. Objetividade máxima. 2. URLs e Links: Forneça links diretos e verificáveis. 3. Arquivos: Estruture saídas em Markdown. Moeda: CAD ($)."},
    "personal": {"name": "Personal Agent", "icon": "👤", "description": "Logística, leitura de documentos e organização.", "language": "pt-BR", "system_prompt": "Você é o Personal Agent. Assistente versátil especializado em decodificar informações, leitura e interpretação de documentos complexos e gestão de rotina (escalas de trabalho, mudança de residência). Simplifique, traduza e organize de forma clara tudo o que for confuso ou burocrático para o usuário."},
    "finance": {"name": "Finance Agent", "icon": "💰", "description": "Planejamento futuro e rotas de saída de dívidas.", "language": "pt-BR", "system_prompt": "Você é o Finance Agent. Especialista em planejamento de futuro, gestão de orçamentos e construção de rotas estratégicas matemáticas para saída de dívidas. Crie planos de ação passo a passo, cronogramas de amortização e estratégias de recuperação financeira. Todas as projeções e cálculos devem ser estruturados em tabelas utilizando Dólar Canadense (CAD / $)."},
    "tech": {"name": "Tech Agent", "icon": "💻", "description": "Otimização extrema, CS2 e hardware.", "language": "pt-BR", "system_prompt": "Você é o Tech Agent. Engenheiro de hardware e software focado em otimização extrema de desempenho, com especialização no jogo CS2. Domina técnicas avançadas como overclock, undervolt, ajustes finos de BIOS, latência de sistema e otimização profunda do Windows. Entregue guias exatos, comandos estruturados e scripts operacionais (PowerShell)."},
    "coach": {"name": "Coach Agent", "icon": "🏋️", "description": "Endocrinologia esportiva e biomecânica.", "language": "pt-BR", "system_prompt": "Você é um Coach de Elite e Especialista em Endocrinologia Esportiva. Prescreva periodizações avançadas (mesociclos, deloads). Analise a via metabólica mTOR, sinalização anabólica e controle de cortisol. Calcule o timing de nutrientes (ovos, frango, carne) para otimizar picos de insulina pós-treino. Diferencie falha mecânica de falha metabólica."},
    "business": {"name": "Business Agent", "icon": "💼", "description": "Geração de renda e marcas faceless.", "language": "pt-BR", "system_prompt": "Você é o Business Agent. Especialista em marketing digital e geração de renda online estruturada através de marcas e canais 'faceless' (sem mostrar o rosto). Desenhe modelos de negócio, roteiros, estratégias de tráfego, automação comercial e monetização utilizando o YouTube e outras plataformas. Calcule projeções em CAD ($)."},
    "english": {"name": "English Teacher", "icon": "🇺🇸", "description": "Transição de idioma e expressões canadenses.", "language": "en-US", "system_prompt": "You are the English Teacher agent. Especialista na transição linguística do Português para o Inglês. Você entende profundamente as dificuldades, os vícios de linguagem e as armadilhas da tradução literal que falantes de português enfrentam. Ofereça suporte total e paciente, explique a lógica por trás da gramática e foque no uso natural do inglês no contexto do Canadá (Ontario)."},
}

current_profile = st.session_state.current_profile
if "current_agent" not in st.session_state: st.session_state.current_agent = "orchestrator"
st.session_state.conversations = st.session_state.long_memory[current_profile].get("history", {a_id: [] for a_id in AGENTS})
for key in ["speech_text", "last_voice_message"]: 
    if key not in st.session_state: st.session_state[key] = ""
if "speech_id" not in st.session_state: st.session_state.speech_id = 0

def auto_web_search(query: str) -> str:
    trigger_words = ["procure", "busque", "pesquise", "internet", "google", "web", "preço", "promoção", "notícia", "hoje", "agora", "bestbuy", "amazon", "mercado"]
    if not any(word in query.lower() for word in trigger_words): return ""
    try:
        results = DDGS().text(query, max_results=3)
        if not results: return ""
        context = "\n[DADOS DA INTERNET EM TEMPO REAL]:\n"
        for r in results: context += f"- Título: {r.get('title')}\n  Link: {r.get('href')}\n  Resumo: {r.get('body')}\n\n"
        return context
    except Exception as e: return f"\n[ERRO NA BUSCA WEB: {str(e)}]"

def ask_deepseek(agent_id: str, history: list[dict[str, Any]], user_query: str, image_base64: str = None) -> str:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
    agent = AGENTS[agent_id]
    memory_facts = "\n- ".join(st.session_state.long_memory[current_profile].get("user_facts", []))
    system_content = f"{agent['system_prompt'].strip()}\n\n[MEMÓRIA DE LONGO PRAZO - PERFIL: {current_profile.upper()}]:\n- {memory_facts}"
    
    web_context = auto_web_search(user_query)
    if web_context: system_content += web_context

    messages = [{"role": "system", "content": system_content}]
    for item in history[-30:]:
        if item.get("role") in {"user", "assistant"} and item.get("content"): 
            messages.append({"role": item["role"], "content": item["content"]})
    
    if image_base64:
        user_msg = messages[-1]
        user_msg["content"] = [
            {"type": "text", "text": user_msg["content"]},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
        ]
    
    response = requests.post(DEEPSEEK_URL, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"model": "deepseek-chat", "messages": messages, "temperature": 0.3}, timeout=60)
    data = response.json()
    if not response.ok: raise RuntimeError(f"DeepSeek: {data.get('error', {}).get('message', 'Erro API')}")
    return data["choices"][0]["message"]["content"].strip()

st.markdown("""<style>
:root { --amoled: #0b141a; --sidebar: #111b21; --bubble-ai: #202c33; --bubble-user: #005c4b; --border: #2a3942; --green: #00a884; --text: #e9edef; --muted: #8696a0; }
.stApp { background: var(--amoled) !important; color: var(--text) !important; }
[data-testid="stHeader"] { background: transparent !important; }
.main .block-container { max-width: 1400px; padding-top: 12px; padding-bottom: 120px; }
[data-testid="stSidebar"] { background: var(--sidebar) !important; border-right: 1px solid var(--border); }
[data-testid="stSidebar"] button { min-height: 52px; width: 100%; border: 0; background: transparent; color: var(--text); text-align: left; padding: 10px 14px; font-size: 15px; }
[data-testid="stSidebar"] button:hover { background: #202c33; }
.chat-header { min-height: 64px; display: flex; align-items: center; gap: 12px; background: var(--bubble-ai); border: 1px solid var(--border); border-radius: 12px; padding: 10px 16px; margin-bottom: 12px; }
.chat-avatar { width: 42px; height: 42px; display: flex; align-items: center; justify-content: center; background: var(--sidebar); border-radius: 50%; font-size: 22px; }
.message-user { display: flex; justify-content: flex-end; margin: 8px 0; }
.message-ai { display: flex; justify-content: flex-start; margin: 8px 0; }
.bubble-user { max-width: 80%; background: var(--bubble-user); border: 1px solid #008069; border-radius: 10px 3px 10px 10px; padding: 10px 14px; font-size: 14px; }
.bubble-ai { max-width: 82%; background: var(--bubble-ai); border: 1px solid var(--border); border-radius: 3px 10px 10px 10px; padding: 10px 14px; font-size: 14px; }
.message-time { color: var(--muted); font-size: 9px; text-align: right; margin-top: 4px; }
</style>""", unsafe_allow_html=True)

COMPOSER_HTML = """<div class="composer-root"><div id="composerStatus" class="composer-status"></div><div class="composer-bar"><textarea id="composerInput" rows="1" placeholder="Digite uma mensagem..."></textarea><button id="micButton" class="composer-button mic-button" type="button" title="Falar">🎙️</button><button id="sendButton" class="composer-button send-button" type="button" title="Enviar">➤</button></div></div>"""
COMPOSER_CSS = ".composer-root { width: 100%; font-family: -apple-system, sans-serif; } .composer-bar { width: 100%; min-height: 50px; display: flex; align-items: center; gap: 8px; padding: 4px 8px 4px 16px; background: #202c33; border: 1px solid #2a3942; border-radius: 25px; } #composerInput { flex: 1; border: 0; outline: 0; background: transparent; color: #e9edef; font-size: 14px; resize: none; max-height: 120px; } .composer-button { width: 38px; height: 38px; border: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 16px; } .mic-button { background: #111b21; color: #8696a0; border: 1px solid #2a3942; } .mic-button.listening { background: #005c4b; color: #fff; } .send-button { background: #00a884; color: #fff; } .composer-status { font-size: 10px; color: #8696a0; padding-left: 16px; height: 14px; }"
COMPOSER_JS = r"""
export default function(component) {
    const { parentElement, data, setTriggerValue } = component;
    if (!parentElement) return;
    const input = parentElement.querySelector("#composerInput"); const micBtn = parentElement.querySelector("#micButton"); const sendBtn = parentElement.querySelector("#sendButton"); const status = parentElement.querySelector("#composerStatus");
    if (!input || !micBtn || !sendBtn) return;
    let rec = null; let lst = false;

    if (data?.speech_text && data?.speech_id !== window.__lastSpeechId) {
        window.__lastSpeechId = data.speech_id;
        if ("speechSynthesis" in window) { window.speechSynthesis.cancel(); const utt = new SpeechSynthesisUtterance(data.speech_text); utt.lang = data.speech_language || "pt-BR"; window.speechSynthesis.speak(utt); }
    }

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { micBtn.style.display = "none"; return; }
    rec = new SR(); rec.lang = data?.input_language || "pt-BR"; rec.continuous = false;
    rec.onresult = (e) => { const txt = e.results[0][0].transcript; input.value = txt; setTriggerValue("voice_message", txt); };
    rec.onstart = () => { lst = true; micBtn.classList.add("listening"); if(status) status.textContent = "Ouvindo..."; };
    rec.onend = () => { lst = false; micBtn.classList.remove("listening"); if(status) status.textContent = ""; };
    micBtn.onclick = () => { if (lst) rec.stop(); else { try { rec.lang = data?.input_language || "pt-BR"; rec.start(); } catch(e){} } };
    const send = () => { const txt = input.value.trim(); if (!txt) return; setTriggerValue("message", txt); input.value = ""; };
    sendBtn.onclick = send; input.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };
}
"""
composer_component = components.component(name="allan_ai_composer", html=COMPOSER_HTML, css=COMPOSER_CSS, js=COMPOSER_JS)

with st.sidebar:
    st.markdown(f'<div style="font-size:20px; font-weight:bold; color:#e9edef; padding:8px 0;">Allan AI</div><div style="font-size:11px; color:#8696a0; margin-bottom:12px;">Logado: <b>{current_profile}</b></div>', unsafe_allow_html=True)
    for a_id, a_data in AGENTS.items():
        sel = (st.session_state.current_agent == a_id)
        if st.button(f"{a_data['icon']} {a_data['name']}", key=f"agent_{a_id}", use_container_width=True, type="primary" if sel else "secondary"):
            if not sel: st.session_state.current_agent = a_id; st.rerun()
    st.markdown("---")
    
    st.caption("Visão Computacional")
    uploaded_file = st.file_uploader("Anexar Imagem", type=["png", "jpg", "jpeg"])
    if uploaded_file is not None:
        st.session_state.image_buffer = base64.b64encode(uploaded_file.getvalue()).decode("utf-8")
        st.success("Imagem carregada.")
    else:
        st.session_state.image_buffer = None

    if st.button("🔒 Sair", use_container_width=True): st.session_state.authenticated = False; st.session_state.current_profile = None; st.rerun()

agent_id = st.session_state.current_agent
agent = AGENTS[agent_id]
st.markdown(f'<div class="chat-header"><div class="chat-avatar">{agent["icon"]}</div><div><div style="font-size:16px;font-weight:bold;color:#e9edef;">{agent["name"]}</div><div style="font-size:12px;color:#8696a0;">{agent["description"]}</div></div></div>', unsafe_allow_html=True)

history = st.session_state.conversations.get(agent_id, [])
st.markdown('<div class="chat-history">', unsafe_allow_html=True)
for msg in history:
    if msg["role"] == "user":
        st.markdown(f'<div class="message-user"><div class="bubble-user">{html.escape(msg["content"])}<div class="message-time">{msg.get("time", "")}</div></div></div>', unsafe_allow_html=True)
    else:
        content_html = re.sub(r"`(.*?)`", r"<pre><code>\1</code></pre>", html.escape(msg["content"]), flags=re.S).replace("\n", "<br>")
        lbl = msg.get("agent", {}).get("name", "Allan AI")
        st.markdown(f'<div class="message-ai"><div class="bubble-ai"><div style="color:#00a884;font-size:11px;font-weight:bold;">{msg.get("agent", {}).get("icon", "🤖")} {lbl}</div>{content_html}<div class="message-time">{msg.get("time", "")}</div></div></div>', unsafe_allow_html=True)
        if "|" in msg["content"] and "\n|" in msg["content"]:
            csv_data = "\n".join([line.replace("|", ",").strip().strip(",") for line in msg["content"].split("\n") if "|" in line])
            st.download_button(label="📥 Baixar Tabela (CSV)", data=csv_data.encode('utf-8'), file_name=f"Data_{int(time.time())}.csv", mime="text/csv", key=f"dl_{msg.get('time')}_{hash(msg['content'][:10])}")
st.markdown('</div>', unsafe_allow_html=True)

c_res = composer_component(key="composer", data={"input_language": agent["language"], "speech_language": agent["language"], "speech_text": st.session_state.speech_text, "speech_id": st.session_state.speech_id}, on_message_change=lambda: None, on_voice_message_change=lambda: None)

def process_msg(text: str):
    if not text: return
    if agent_id not in st.session_state.conversations: st.session_state.conversations[agent_id] = []
    
    img_b64 = st.session_state.get("image_buffer")
    msg_content = f"[Imagem Anexada] {text}" if img_b64 else text

    st.session_state.conversations[agent_id].append({"role": "user", "content": msg_content, "time": time.strftime("%H:%M"), "agent": agent})
    st.session_state.long_memory[current_profile]["history"] = st.session_state.conversations
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f: json.dump(st.session_state.long_memory, f, ensure_ascii=False)
    except: pass
    
    try:
        with st.spinner("Analisando..."): ans = ask_deepseek(agent_id, st.session_state.conversations[agent_id], text, img_b64)
        st.session_state.conversations[agent_id].append({"role": "assistant", "content": ans, "time": time.strftime("%H:%M"), "agent": agent})
        st.session_state.speech_text = re.sub(r"`.*?`|[*_#>|]", " ", ans, flags=re.S).strip()
        st.session_state.speech_id += 1
        st.session_state.image_buffer = None
    except Exception as e:
        st.session_state.conversations[agent_id].append({"role": "assistant", "content": f"Erro: {e}", "time": time.strftime("%H:%M"), "agent": {"icon": "⚠️", "name": "Erro"}})

v_trig, m_trig = getattr(c_res, "voice_message", None), getattr(c_res, "message", None)
if v_trig and str(v_trig) != st.session_state.last_voice_message:
    st.session_state.last_voice_message = str(v_trig); process_msg(str(v_trig)); st.rerun()
elif m_trig and str(m_trig):
    process_msg(str(m_trig)); st.rerun()