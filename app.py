import html
import json
import os
import re
import time
import hashlib
from typing import Any
import base64

import requests
import streamlit as st
import streamlit.components.v2 as components
from duckduckgo_search import DDGS
from supabase import create_client, Client

st.set_page_config(page_title="ROG AI - Cloud Memory", page_icon="🔒", layout="wide", initial_sidebar_state="expanded")

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
MEMORY_FILE = "long_term_memory.json"

PASSWORDS = {
    "Allan": st.secrets.get("ALLAN_PASSWORD", "Allan2026@Pass"),
    "Beatriz": st.secrets.get("BEATRIZ_PASSWORD", "Beatriz2026@Pass"),
    "Irmao_1": st.secrets.get("IRMAO1_PASSWORD", "Irmao1@Pass"),
    "Irmao_2": st.secrets.get("IRMAO2_PASSWORD", "Irmao2@Pass")
}

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

@st.cache_resource
def init_supabase() -> Client | None:
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None

supabase = init_supabase()

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "current_profile" not in st.session_state: st.session_state.current_profile = None

if not st.session_state.authenticated:
    st.markdown("<style>.stApp { background-color: #0b141a !important; color: #e9edef !important; } .login-box { max-width: 400px; margin: 100px auto; padding: 30px; background: #202c33; border-radius: 12px; border: 1px solid #2a3942; text-align: center; }</style>", unsafe_allow_html=True)
    st.markdown("<div class='login-box'>", unsafe_allow_html=True)
    st.title("🔒 ROG AI")
    profile_choice = st.selectbox("Perfil", ["Allan", "Beatriz", "Irmao_1", "Irmao_2"])
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
        "TRABALHO: Setor de limpeza no Canadá com colega Serdar. Sem diploma.",
        "METAS: Plano de CAD $5.000 (faculdade Beatriz) para set/2026. Troca do Mazda 3 (2012).",
        "TECH & GAMES: Joga CS2 competitivo. Monta PCs de alta performance.",
        "FITNESS: Musculação na Crunch Fitness. Dieta hiperproteica.",
        "ESTILO: Racional, lógico, sem clichês. Respostas densas e objetivas.",
        "MOEDA: Dólar Canadense (CAD / $)."
    ],
    "Beatriz": [
        "IDENTIDADE: Beatriz. Casada com Allan Vitor Portello.",
        "ESTUDOS E TRABALHO: Formada em agronomia, gestão de negócios. Trabalha na A&W.",
        "LOCALIZAÇÃO: Hamilton, Ontario (mudando para Brantford em set/2026).",
        "METAS FINANCEIRAS: Parcelamento universitário de CAD $5.000 para set/2026.",
        "FITNESS: Treino e dieta alinhados à rotina.",
        "MOEDA: Dólar Canadense (CAD / $)."
    ],
    "Irmao_1": ["IDENTIDADE: Usuário Irmão 1.", "DIRETRIZES: Acesso total às engines de otimização técnica, financeira e linguística da ROG AI."],
    "Irmao_2": ["IDENTIDADE: Usuário Irmão 2.", "DIRETRIZES: Acesso total às engines de otimização técnica, financeira e linguística da ROG AI."]
}

def load_long_term_memory() -> dict:
    base = {p: {"user_facts": PROFILES[p].copy(), "history": {}} for p in PROFILES}
    if supabase:
        try:
            response = supabase.table("long_term_memory").select("*").execute()
            for row in response.data:
                p = row["profile"]
                if p in base:
                    base[p]["history"] = row.get("history", {})
                    base[p]["user_facts"] = list(set(PROFILES[p] + row.get("user_facts", [])))
            return base
        except Exception: pass
    
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for p in PROFILES:
                if p in saved:
                    base[p]["history"] = saved[p].get("history", {})
                    base[p]["user_facts"] = list(set(PROFILES[p] + saved[p].get("user_facts", [])))
        except Exception: pass
    return base

def save_long_term_memory(memory_data: dict) -> None:
    if supabase:
        try:
            for p, data in memory_data.items():
                supabase.table("long_term_memory").upsert({"profile": p, "user_facts": data.get("user_facts", []), "history": data.get("history", {})}).execute()
        except Exception: pass
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f: json.dump(memory_data, f, ensure_ascii=False, indent=2)
    except Exception: pass

if "long_memory" not in st.session_state: st.session_state.long_memory = load_long_term_memory()
if "last_payload_hash" not in st.session_state: st.session_state.last_payload_hash = ""

AGENTS = {
    "orchestrator": {"name": "ROG AI Core", "icon": "🤖", "description": "Inteligência central e triagem.", "language": "pt-BR", "api_model": "deepseek-chat", "system_prompt": "Você é o ROG AI Core. Diretrizes estritas: 1. Objetividade máxima. 2. Links diretos. 3. Formatação Markdown."},
    "personal": {"name": "Personal Agent", "icon": "👤", "description": "Logística, leitura de documentos.", "language": "pt-BR", "api_model": "deepseek-chat", "system_prompt": "Você é o Personal Agent. Especialista em decodificar informações, leitura de documentos e gestão de rotina. Simplifique e traduza dados burocráticos."},
    "finance": {"name": "Finance Agent", "icon": "💰", "description": "Planejamento futuro e rotas.", "language": "pt-BR", "api_model": "deepseek-reasoner", "system_prompt": "Você é o Finance Agent. Especialista em planejamento de futuro e rotas matemáticas para saída de dívidas. Crie planos de ação e cronogramas de amortização estruturados em tabelas."},
    "tech": {"name": "Tech Agent", "icon": "💻", "description": "Otimização extrema, CS2 e hardware.", "language": "pt-BR", "api_model": "deepseek-reasoner", "system_prompt": "Você é o Tech Agent. Engenheiro focado em otimização de desempenho, CS2, overclock, undervolt, BIOS e latência. Entregue scripts operacionais e comandos exatos."},
    "coach": {"name": "Coach Agent", "icon": "🏋️", "description": "Endocrinologia esportiva e biomecânica.", "language": "pt-BR", "api_model": "deepseek-chat", "system_prompt": "Você é um Coach de Elite e Especialista em Endocrinologia Esportiva. Prescreva periodizações (mesociclos). Analise sinalização anabólica e timing de nutrientes. Diferencie falha mecânica de metabólica."},
    "business": {"name": "Business Agent", "icon": "💼", "description": "Geração de renda e marcas faceless.", "language": "pt-BR", "api_model": "deepseek-reasoner", "system_prompt": "Você é o Business Agent. Estrategista de modelos de negócio 'faceless'. Desenhe roteiros, tráfego e monetização em plataformas digitais."},
    "english": {"name": "English Teacher", "icon": "🇺🇸", "description": "Transição linguística.", "language": "en-US", "api_model": "deepseek-chat", "system_prompt": "You are the English Teacher. Especialista em transição do Português para o Inglês. Corrija vícios de tradução literal. Foque no uso natural do inglês Canadense."},
}

current_profile = st.session_state.current_profile
if "current_agent" not in st.session_state: st.session_state.current_agent = "orchestrator"
st.session_state.conversations = st.session_state.long_memory[current_profile].get("history", {a_id: [] for a_id in AGENTS})

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
    target_model = agent.get("api_model", "deepseek-chat")
    
    memory_facts = "\n- ".join(st.session_state.long_memory[current_profile].get("user_facts", []))
    system_content = f"{agent['system_prompt'].strip()}\n\n[MEMÓRIA - PERFIL: {current_profile.upper()}]:\n- {memory_facts}"
    
    web_context = auto_web_search(user_query)
    if web_context: system_content += web_context

    messages = [{"role": "system", "content": system_content}]
    for item in history[-30:]:
        if item.get("role") in {"user", "assistant"} and item.get("content"): 
            messages.append({"role": item["role"], "content": item["content"]})
    
    if image_base64:
        user_msg = messages[-1]
        user_msg["content"] = [{"type": "text", "text": user_msg["content"]}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}]
    
    response = requests.post(DEEPSEEK_URL, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"model": target_model, "messages": messages, "temperature": 0.3}, timeout=90)
    data = response.json()
    if not response.ok: raise RuntimeError(f"DeepSeek: {data.get('error', {}).get('message', 'Erro API')}")
    
    reasoning = data["choices"][0]["message"].get("reasoning_content", "")
    content = data["choices"][0]["message"].get("content", "")
    return f"> *Raciocínio lógico executado pelo motor DeepSeek-R1.*\n\n{content}" if reasoning and target_model == "deepseek-reasoner" else content.strip()

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

COMPOSER_HTML = """
<div class="composer-root">
    <div id="imagePreview" class="image-preview" style="display:none;"><img id="previewImg" src=""><span id="removeImg">✖</span></div>
    <div id="composerStatus" class="composer-status"></div>
    <div class="composer-bar">
        <input type="file" id="fileInput" accept="image/png, image/jpeg" style="display:none;">
        <button id="attachBtn" class="composer-button attach-button" type="button" title="Anexar Imagem">📎</button>
        <textarea id="composerInput" rows="1" placeholder="Digite uma mensagem..."></textarea>
        <button id="micButton" class="composer-button mic-button" type="button" title="Falar">🎙️</button>
        <button id="sendButton" class="composer-button send-button" type="button" title="Enviar">➤</button>
    </div>
</div>
"""
COMPOSER_CSS = """
.composer-root { width: 100%; font-family: -apple-system, sans-serif; position: relative; }
.composer-bar { width: 100%; min-height: 50px; display: flex; align-items: center; gap: 8px; padding: 4px 8px 4px 8px; background: #202c33; border: 1px solid #2a3942; border-radius: 25px; }
#composerInput { flex: 1; border: 0; outline: 0; background: transparent; color: #e9edef; font-size: 14px; resize: none; max-height: 120px; }
.composer-button { width: 38px; height: 38px; border: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 16px; }
.attach-button { background: transparent; color: #8696a0; font-size: 18px; margin-left: 4px; } .attach-button:hover { color: #e9edef; }
.mic-button { background: #111b21; color: #8696a0; border: 1px solid #2a3942; } .mic-button.listening { background: #005c4b; color: #fff; } .send-button { background: #00a884; color: #fff; }
.composer-status { font-size: 10px; color: #8696a0; padding-left: 16px; height: 14px; }
.image-preview { position: absolute; bottom: 60px; left: 16px; background: #202c33; padding: 4px; border-radius: 8px; border: 1px solid #2a3942; }
.image-preview img { max-height: 80px; border-radius: 4px; }
#removeImg { position: absolute; top: -8px; right: -8px; background: #00a884; color: white; border-radius: 50%; width: 20px; height: 20px; text-align: center; font-size: 12px; line-height: 20px; cursor: pointer; font-weight: bold; }
"""
COMPOSER_JS = r"""
export default function(component) {
    const { parentElement, data, setTriggerValue } = component;
    if (!parentElement) return;
    const input = parentElement.querySelector("#composerInput"); const micBtn = parentElement.querySelector("#micButton"); const sendBtn = parentElement.querySelector("#sendButton"); const status = parentElement.querySelector("#composerStatus");
    const attachBtn = parentElement.querySelector("#attachBtn"); const fileInput = parentElement.querySelector("#fileInput"); const previewDiv = parentElement.querySelector("#imagePreview"); const previewImg = parentElement.querySelector("#previewImg"); const removeImg = parentElement.querySelector("#removeImg");
    if (!input || !micBtn || !sendBtn || !attachBtn) return;
    
    let base64Image = null;
    attachBtn.onclick = () => fileInput.click();
    fileInput.onchange = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (ev) => {
            base64Image = ev.target.result.split(',')[1];
            previewImg.src = ev.target.result;
            previewDiv.style.display = "block";
        };
        reader.readAsDataURL(file);
    };
    removeImg.onclick = () => { base64Image = null; fileInput.value = ""; previewDiv.style.display = "none"; };

    let rec = null; let lst = false;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { micBtn.style.display = "none"; } else {
        rec = new SR(); rec.lang = data?.input_language || "pt-BR"; rec.continuous = false;
        rec.onresult = (e) => { 
            const txt = e.results[0][0].transcript; 
            input.value = txt; 
            setTriggerValue({text: txt, image: base64Image, type: "voice"});
            base64Image = null; previewDiv.style.display = "none"; fileInput.value = "";
        };
        rec.onstart = () => { lst = true; micBtn.classList.add("listening"); if(status) status.textContent = "Ouvindo..."; };
        rec.onend = () => { lst = false; micBtn.classList.remove("listening"); if(status) status.textContent = ""; };
        micBtn.onclick = () => { if (lst) rec.stop(); else { try { rec.lang = data?.input_language || "pt-BR"; rec.start(); } catch(e){} } };
    }

    const send = () => { 
        const txt = input.value.trim(); 
        if (!txt && !base64Image) return; 
        setTriggerValue({text: txt, image: base64Image, type: "text"}); 
        input.value = ""; base64Image = null; fileInput.value = ""; previewDiv.style.display = "none";
    };
    sendBtn.onclick = send; input.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };
}
"""
composer_component = components.component(name="rog_ai_composer", html=COMPOSER_HTML, css=COMPOSER_CSS, js=COMPOSER_JS)

with st.sidebar:
    st.markdown(f'<div style="font-size:20px; font-weight:bold; color:#e9edef; padding:8px 0;">ROG AI</div><div style="font-size:11px; color:#8696a0; margin-bottom:12px;">Logado: <b>{current_profile}</b></div>', unsafe_allow_html=True)
    for a_id, a_data in AGENTS.items():
        sel = (st.session_state.current_agent == a_id)
        if st.button(f"{a_data['icon']} {a_data['name']}", key=f"agent_{a_id}", use_container_width=True, type="primary" if sel else "secondary"):
            if not sel: st.session_state.current_agent = a_id; st.rerun()
    st.markdown("---")
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
        lbl = msg.get("agent", {}).get("name", "ROG AI")
        st.markdown(f'<div class="message-ai"><div class="bubble-ai"><div style="color:#00a884;font-size:11px;font-weight:bold;">{msg.get("agent", {}).get("icon", "🤖")} {lbl}</div>{content_html}<div class="message-time">{msg.get("time", "")}</div></div></div>', unsafe_allow_html=True)
        if "|" in msg["content"] and "\n|" in msg["content"]:
            csv_data = "\n".join([line.replace("|", ",").strip().strip(",") for line in msg["content"].split("\n") if "|" in line])
            st.download_button(label="📥 Baixar Tabela (CSV)", data=csv_data.encode('utf-8'), file_name=f"Data_{int(time.time())}.csv", mime="text/csv", key=f"dl_{msg.get('time')}_{hash(msg['content'][:10])}")
st.markdown('</div>', unsafe_allow_html=True)

c_res = composer_component(key="composer", data={"input_language": agent["language"]}, on_change=lambda: None)

def process_msg(text: str, img_b64: str = None):
    if not text and not img_b64: return
    if agent_id not in st.session_state.conversations: st.session_state.conversations[agent_id] = []
    
    msg_content = f"[Imagem Anexada] {text}" if img_b64 else text

    st.session_state.conversations[agent_id].append({"role": "user", "content": msg_content, "time": time.strftime("%H:%M"), "agent": agent})
    st.session_state.long_memory[current_profile]["history"] = st.session_state.conversations
    save_long_term_memory(st.session_state.long_memory)
    
    try:
        with st.spinner("Processamento DeepSeek R1..." if agent.get("api_model") == "deepseek-reasoner" else "Analisando..."): 
            ans = ask_deepseek(agent_id, st.session_state.conversations[agent_id], text, img_b64)
        st.session_state.conversations[agent_id].append({"role": "assistant", "content": ans, "time": time.strftime("%H:%M"), "agent": agent})
    except Exception as e:
        st.session_state.conversations[agent_id].append({"role": "assistant", "content": f"Erro: {e}", "time": time.strftime("%H:%M"), "agent": {"icon": "⚠️", "name": "Erro"}})

if c_res and isinstance(c_res, dict):
    txt_val = c_res.get("text", "")
    img_val = c_res.get("image")
    m_type = c_res.get("type", "")
    payload_hash = hashlib.md5(f"{txt_val}_{img_val}_{m_type}".encode()).hexdigest()
    
    if payload_hash != st.session_state.last_payload_hash:
        st.session_state.last_payload_hash = payload_hash
        process_msg(txt_val, img_val)
        st.rerun()