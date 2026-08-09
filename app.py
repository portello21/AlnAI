import html
import json
import os
import re
import time
import hashlib
import datetime
from typing import Any
import base64

import requests
import streamlit as st
import streamlit.components.v2 as components
import extra_streamlit_components as stx
from duckduckgo_search import DDGS
from supabase import create_client, Client

st.set_page_config(page_title="ROG AI - Cloud Memory", page_icon="🔒", layout="wide", initial_sidebar_state="expanded")

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
MEMORY_FILE = "long_term_memory.json"

PASSWORDS = {
    "Allan": st.secrets.get("ALLAN_PASSWORD", "Allan2026@Pass"),
    "Beatriz": st.secrets.get("BEATRIZ_PASSWORD", "Beatriz2026@Pass"),
    "Natan": st.secrets.get("NATAN_PASSWORD", "Natan@Pass"),
    "Tainan": st.secrets.get("TAINAN_PASSWORD", "Tainan@Pass")
}

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

@st.cache_resource
def init_supabase() -> Client | None:
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None

supabase = init_supabase()
cookie_manager = stx.CookieManager(key="rog_cookies")

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "current_profile" not in st.session_state: st.session_state.current_profile = None

cookie_profile = cookie_manager.get(cookie="rog_ai_profile")
if cookie_profile in PASSWORDS and not st.session_state.authenticated:
    st.session_state.authenticated = True
    st.session_state.current_profile = cookie_profile
    st.rerun()

if not st.session_state.authenticated:
    st.markdown("""
    <style>
    .stApp { background: radial-gradient(circle at 50% 10%, rgba(0,168,132,.10), transparent 30%), linear-gradient(180deg,#070b0e,#0b141a) !important; color:#e9edef !important; }
    [data-testid="stHeader"] { background:transparent !important; }
    .main .block-container { max-width:430px; min-height:78vh; padding:52px 34px 30px; background:linear-gradient(145deg,#121d23,#0c1419); border:1px solid #263840; border-radius:24px; box-shadow:0 25px 80px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.02); }
    .rog-login-shell { padding:4px 0 20px; text-align:center; }
    .rog-login-mark { width:68px; height:68px; margin:0 auto 16px; display:flex; align-items:center; justify-content:center; border-radius:19px; background:linear-gradient(145deg,#123d35,#0d211d); border:1px solid rgba(0,168,132,.45); color:#36d9b3; font-size:30px; font-weight:800; }
    .rog-login-title { color:#eef3f5; font-size:28px; font-weight:760; letter-spacing:-.7px; }
    .rog-login-subtitle { color:#84939c; font-size:13px; margin:5px 0 22px; }
    .rog-login-divider { height:1px; background:#263840; margin-bottom:20px; }
    div[data-testid="stSelectbox"] label, div[data-testid="stTextInput"] label { color:#a9b6bc !important; font-size:12px !important; }
    div[data-testid="stSelectbox"] > div > div, div[data-testid="stTextInput"] input { background:#0b141a !important; color:#e9edef !important; border:1px solid #2a3942 !important; border-radius:12px !important; }
    div[data-testid="stTextInput"] input:focus { border-color:#00a884 !important; box-shadow:0 0 0 1px #00a884 !important; }
    div[data-testid="stCheckbox"] label { color:#8696a0 !important; font-size:12px !important; }
    .rog-login-footer { color:#596970; font-size:10px; margin-top:18px; letter-spacing:.4px; text-align:center; }
    </style>
    <div class="rog-login-shell">
        <div class="rog-login-mark">R</div>
        <div class="rog-login-title">ROG AI</div>
        <div class="rog-login-subtitle">Inteligência multiagente · memória privada · acesso seguro</div>
        <div class="rog-login-divider"></div>
    </div>
    """, unsafe_allow_html=True)
    profile_choice = st.selectbox("Perfil", ["Allan", "Beatriz", "Natan", "Tainan"])
    input_pass = st.text_input("Senha", type="password")
    lembrar_me = st.checkbox("Lembrar de mim (30 dias)")
    if st.button("Entrar", use_container_width=True, type="primary"):
        if input_pass == PASSWORDS[profile_choice]:
            st.session_state.authenticated = True
            st.session_state.current_profile = profile_choice
            if lembrar_me:
                cookie_manager.set("rog_ai_profile", profile_choice, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
            st.rerun()
        else:
            st.error("Falha de autenticação.")
    st.markdown('<div class="rog-login-footer">ROG AI · acesso autenticado</div>', unsafe_allow_html=True)
    st.stop()

PROFILES = {
    "Allan": ["IDENTIDADE: Allan Vitor Portello, 26 anos (21/04/2000). Altura: 1.90m, Peso: ~118.9kg.", "FAMÍLIA: Casado com Beatriz (agronomia/A&W).", "LOCALIZAÇÃO: Hamilton, Ontario (mudando para Brantford em set/2026).", "TRABALHO: Setor de limpeza no Canadá com colega Serdar. Sem diploma.", "METAS: Plano de CAD 5.000 (faculdade Beatriz) para set/2026. Troca do Mazda 3 (2012).", "TECH & GAMES: Joga CS2 competitivo. Monta PCs de alta performance.", "FITNESS: Musculação na Crunch Fitness. Dieta hiperproteica.", "ESTILO: Racional, lógico, sem clichês. Respostas densas e objetivas.", "MOEDA: Dólar Canadense (CAD)."],
    "Beatriz": ["IDENTIDADE: Beatriz. Casada com Allan Vitor Portello.", "ESTUDOS E TRABALHO: Formada em agronomia, gestão de negócios. Trabalha na A&W.", "LOCALIZAÇÃO: Hamilton, Ontario (mudando para Brantford em set/2026).", "METAS FINANCEIRAS: Parcelamento universitário de CAD 5.000 para set/2026.", "FITNESS: Treino e dieta alinhados à rotina.", "MOEDA: Dólar Canadense (CAD)."],
    "Natan": ["IDENTIDADE: Usuário Natan (Irmão de Allan).", "DIRETRIZES: Acesso total às engines de otimização técnica, financeira e linguística da ROG AI."],
    "Tainan": ["IDENTIDADE: Usuário Tainan (Irmão de Allan).", "DIRETRIZES: Acesso total às engines de otimização técnica, financeira e linguística da ROG AI."]
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

st.markdown("""
<style>
:root { --amoled:#080d10; --sidebar:#0e171c; --sidebar-2:#111c22; --bubble-ai:#172229; --bubble-user:#075e54; --border:#263840; --border-soft:rgba(134,150,160,.14); --green:#00a884; --text:#e9edef; --muted:#8696a0; }
.stApp { background:radial-gradient(circle at 75% -10%,rgba(0,168,132,.055),transparent 30%),linear-gradient(180deg,#080d10 0%,#0b141a 100%) !important; color:var(--text) !important; }
[data-testid="stHeader"] { background:transparent !important; }
[data-testid="stAppViewContainer"] { background:transparent !important; }
.main .block-container { max-width:1480px; padding:10px 18px 105px; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#0e171c 0%,#0b141a 100%) !important; border-right:1px solid var(--border) !important; }
[data-testid="stSidebar"] > div:first-child { padding-top:12px; }
[data-testid="stSidebar"] .stButton { margin:2px 0 !important; }
[data-testid="stSidebar"] .stButton > button { min-height:58px !important; border:1px solid transparent !important; border-left:3px solid transparent !important; border-radius:11px !important; background:transparent !important; color:var(--text) !important; text-align:left !important; padding:8px 12px !important; font-size:14px !important; font-weight:550 !important; box-shadow:none !important; transition:background .16s ease,border-color .16s ease,transform .16s ease; }
[data-testid="stSidebar"] .stButton > button:hover { background:#17232a !important; border-color:var(--border-soft) !important; border-left-color:#00a884 !important; transform:translateX(1px); }
[data-testid="stSidebar"] .stButton > button[kind="primary"] { background:linear-gradient(90deg,rgba(0,168,132,.16),rgba(0,168,132,.06)) !important; border-color:rgba(0,168,132,.18) !important; border-left-color:var(--green) !important; }
[data-testid="stSidebar"] hr { border-color:var(--border) !important; margin:16px 0 !important; }
.rog-sidebar-head { padding:8px 4px 18px; }
.rog-brand-row { display:flex; align-items:center; gap:10px; }
.rog-brand-mark { width:38px; height:38px; border-radius:11px; display:flex; align-items:center; justify-content:center; background:linear-gradient(145deg,#123c34,#10241f); border:1px solid rgba(0,168,132,.34); color:#32d5b0; font-weight:800; }
.rog-brand-title { color:var(--text); font-size:20px; font-weight:760; letter-spacing:-.4px; }
.rog-brand-subtitle { color:var(--muted); font-size:11px; margin-top:2px; }
.rog-profile-chip { display:inline-flex; align-items:center; gap:6px; margin-top:13px; padding:5px 9px; border:1px solid var(--border); border-radius:999px; color:#9eabb1; background:#0b141a; font-size:10px; }
.rog-section-label { color:#5f7078; font-size:9px; font-weight:800; letter-spacing:1.4px; margin:0 4px 5px; }
.chat-header { min-height:70px; display:flex; align-items:center; gap:13px; background:rgba(17,28,34,.92); border:1px solid var(--border); border-radius:15px; padding:10px 16px; margin-bottom:13px; box-shadow:0 8px 28px rgba(0,0,0,.16),inset 0 1px 0 rgba(255,255,255,.02); backdrop-filter:blur(10px); }
.chat-avatar { width:46px; height:46px; flex:0 0 46px; display:flex; align-items:center; justify-content:center; background:linear-gradient(145deg,#1a2a31,#0d171c); border:1px solid #344750; border-radius:14px; font-size:23px; }
.chat-agent-name { color:var(--text); font-size:16px; font-weight:700; letter-spacing:-.2px; }
.chat-agent-description { color:var(--muted); font-size:11px; margin-top:3px; }
.chat-header::after { content:'● ONLINE'; margin-left:auto; color:#00a884; font-size:9px; letter-spacing:.9px; font-weight:800; opacity:.9; }
.chat-history { padding:6px 3.5% 32px; }
.message-user,.message-ai { display:flex; width:100%; margin:7px 0; }
.message-user { justify-content:flex-end; }
.message-ai { justify-content:flex-start; }
.bubble-user,.bubble-ai { position:relative; line-height:1.55; font-size:14px; box-shadow:0 2px 7px rgba(0,0,0,.18); }
.bubble-user { max-width:min(760px,80%); background:linear-gradient(145deg,#075e54,#075449); border:1px solid #0a806f; border-radius:14px 4px 14px 14px; padding:10px 13px 7px; }
.bubble-ai { max-width:min(820px,84%); background:linear-gradient(145deg,#172229,#152027); border:1px solid var(--border); border-radius:4px 14px 14px 14px; padding:10px 14px 7px; }
.bubble-ai > div:first-child { color:#35cfae !important; font-size:10px !important; font-weight:800 !important; letter-spacing:.2px; margin-bottom:7px; }
.message-time { color:rgba(233,237,239,.48); font-size:9px; text-align:right; margin-top:5px; }
.bubble-ai pre,.bubble-user pre { background:#0b141a; border:1px solid #263840; border-radius:9px; padding:12px; overflow-x:auto; margin:9px 0 4px; }
.bubble-ai code,.bubble-user code { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:12px; }
.bubble-ai table,.bubble-user table { width:100%; border-collapse:collapse; margin:9px 0; font-size:12px; }
.bubble-ai th,.bubble-ai td,.bubble-user th,.bubble-user td { border:1px solid #304149; padding:6px 8px; }
.bubble-ai th,.bubble-user th { background:#0f1a20; color:#b9c5ca; }
.composer-root { position:relative; }
.composer-bar { box-shadow:0 12px 35px rgba(0,0,0,.38) !important; backdrop-filter:blur(14px); }
[data-testid="stDownloadButton"] button { background:#111c22 !important; border:1px solid #263840 !important; color:#9eabb1 !important; border-radius:9px !important; font-size:11px !important; min-height:32px !important; }
[data-testid="stDownloadButton"] button:hover { border-color:#00a884 !important; color:#e9edef !important; }
@media (max-width:900px) { .main .block-container { padding:8px 8px 95px; } .chat-history { padding-left:1%; padding-right:1%; } .bubble-user { max-width:90%; } .bubble-ai { max-width:94%; } .chat-header::after { display:none; } }
</style>
""", unsafe_allow_html=True)

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
    st.markdown(f"""
        <div class="rog-sidebar-head">
            <div class="rog-brand-row">
                <div class="rog-brand-mark">R</div>
                <div>
                    <div class="rog-brand-title">ROG AI</div>
                    <div class="rog-brand-subtitle">Multiagent Intelligence</div>
                </div>
            </div>
            <div class="rog-profile-chip">● {current_profile} · sessão ativa</div>
        </div>
        <div class="rog-section-label">AGENTES ESPECIALISTAS</div>
    """, unsafe_allow_html=True)
    for a_id, a_data in AGENTS.items():
        sel = (st.session_state.current_agent == a_id)
        if st.button(f"{a_data['icon']}  {a_data['name']}", key=f"agent_{a_id}", use_container_width=True, type="primary" if sel else "secondary"):
            if not sel: st.session_state.current_agent = a_id; st.rerun()
    st.markdown('<div class="rog-section-label" style="margin-top:18px;">CONTA</div>', unsafe_allow_html=True)
    if st.button("↪  Sair da sessão", use_container_width=True):
        cookie_manager.delete("rog_ai_profile")
        st.session_state.authenticated = False
        st.session_state.current_profile = None
        st.rerun()

agent_id = st.session_state.current_agent
agent = AGENTS[agent_id]
st.markdown(f"""
<div class="chat-header">
    <div class="chat-avatar">{agent["icon"]}</div>
    <div>
        <div class="chat-agent-name">{html.escape(agent["name"])}</div>
        <div class="chat-agent-description">{html.escape(agent["description"])}</div>
    </div>
</div>
""", unsafe_allow_html=True)

history = st.session_state.conversations.get(agent_id, [])
st.markdown('<div class="chat-history">', unsafe_allow_html=True)
for msg in history:
    if msg["role"] == "user":
        st.markdown(f"""
<div class="message-user">
    <div class="bubble-user">
        {html.escape(msg["content"])}
        <div class="message-time">{html.escape(msg.get("time", ""))}</div>
    </div>
</div>
""", unsafe_allow_html=True)
    else:
        content_html = re.sub(r"`(.*?)`", r"<pre><code>\1</code></pre>", html.escape(msg["content"]), flags=re.S).replace("\n", "<br>")
        lbl = msg.get("agent", {}).get("name", "ROG AI")
        st.markdown(f"""
<div class="message-ai">
    <div class="bubble-ai">
        <div>{msg.get("agent", {}).get("icon", "🤖")} {html.escape(lbl)}</div>
        {content_html}
        <div class="message-time">{html.escape(msg.get("time", ""))}</div>
    </div>
</div>
""", unsafe_allow_html=True)
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