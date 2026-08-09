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
from duckduckgo_search import DDGS
from supabase import create_client, Client

st.set_page_config(page_title="ROG AI - Advanced Core", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

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

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "current_profile" not in st.session_state: st.session_state.current_profile = None

if not st.session_state.authenticated:
    url_token = st.query_params.get("auth")
    if url_token:
        for profile_name, password in PASSWORDS.items():
            if url_token == hashlib.md5(password.encode()).hexdigest():
                st.session_state.authenticated = True
                st.session_state.current_profile = profile_name
                break

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

AGENTS = {
    "orchestrator": {
        "name": "ROG AI Core", 
        "icon": "🧠", 
        "description": "Inteligência primária com visão OCR.", 
        "language": "pt-BR", 
        "api_model": "deepseek-chat", 
        "system_prompt": "Você é a ROG AI, a inteligência artificial primária de elite do usuário atual, equipada com capacidade de análise visual e OCR. Extraia dados de imagens anexadas, analise recibos, faturas e documentos, respondendo com precisão analítica e sem filtros corporativos."
    },
    "personal": {"name": "Personal Agent", "icon": "👤", "description": "Logística e leitura de documentos.", "language": "pt-BR", "api_model": "deepseek-chat", "system_prompt": "Você é o Personal Agent. Leia documentos burocráticos, traduza burocracias e otimize a rotina logística."},
    "finance": {"name": "Finance Agent", "icon": "💰", "description": "Planejamento e rotas matemáticas.", "language": "pt-BR", "api_model": "deepseek-reasoner", "system_prompt": "Você é o Finance Agent. Estruture saídas de dívidas e planilhas de longo prazo matemáticas em CAD."},
    "tech": {"name": "Tech Agent", "icon": "💻", "description": "Otimização Windows, Hardware e CS2.", "language": "pt-BR", "api_model": "deepseek-reasoner", "system_prompt": "Você é o Tech Agent. Especialista em latência, undervolt, otimização do Windows e engenharia para ganho de FPS no CS2."},
    "coach": {"name": "Coach Agent", "icon": "🏋️", "description": "Endocrinologia e biomecânica.", "language": "pt-BR", "api_model": "deepseek-chat", "system_prompt": "Você é o Coach Agent. Foque na via metabólica mTOR, anabolismo, timing de nutrientes e periodizações intensas."},
    "business": {"name": "Business Agent", "icon": "💼", "description": "Geração de renda digital.", "language": "pt-BR", "api_model": "deepseek-reasoner", "system_prompt": "Você é o Business Agent. Desenhe negócios online 'faceless', tráfego e monetização passo a passo."},
    "english": {"name": "English Teacher", "icon": "🇺🇸", "description": "Fluência extrema e gramática.", "language": "en-US", "api_model": "deepseek-chat", "system_prompt": "Você é o English Teacher. Destrua os vícios de tradução do português. Foque na fluência real do Canadá."},
}

if "current_agent" not in st.session_state: st.session_state.current_agent = "orchestrator"

def auto_web_search(query: str) -> str:
    trigger_words = ["procure", "busque", "pesquise", "internet", "google", "web", "preço", "promoção", "notícia", "hoje", "agora", "bestbuy", "amazon"]
    if not any(word in query.lower() for word in trigger_words): return ""
    try:
        results = DDGS().text(query, max_results=3)
        if not results: return ""
        context = "\\n[DADOS DA INTERNET EM TEMPO REAL]:\\n"
        for r in results: context += f"- Título: {r.get('title')}\\n  Link: {r.get('href')}\\n  Resumo: {r.get('body')}\\n\\n"
        return context
    except Exception as e: return f"\\n[ERRO BUSCA WEB: {str(e)}]"

def ask_deepseek(agent_id: str, history: list, user_query: str, image_b64: str = None) -> str:
    api_key = st.secrets["DEEPSEEK_API_KEY"]
    agent = AGENTS[agent_id]
    target_model = agent.get("api_model", "deepseek-chat")
    
    memory_facts = "\\n- ".join(st.session_state.long_memory[st.session_state.current_profile].get("user_facts", []))
    system_content = f"{agent['system_prompt'].strip()}\\n\\n[MEMÓRIA - PERFIL: {st.session_state.current_profile.upper()}]:\\n- {memory_facts}"
    
    web_context = auto_web_search(user_query)
    if web_context: system_content += web_context

    messages = [{"role": "system", "content": system_content}]
    for item in history[-30:]:
        if item.get("role") in {"user", "assistant"} and item.get("content"): 
            messages.append({"role": item["role"], "content": item["content"]})
            
    if image_b64 and messages:
        # Insere a imagem estruturada no formato compatível de visão
        last_msg = messages[-1]
        if isinstance(last_msg["content"], str):
            last_msg["content"] = [
                {"type": "text", "text": last_msg["content"]},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
            ]
    
    try:
        response = requests.post(DEEPSEEK_URL, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"model": target_model, "messages": messages, "temperature": 0.3}, timeout=120)
        response.raise_for_status()
        data = response.json()
        reasoning = data["choices"][0]["message"].get("reasoning_content", "")
        content = data["choices"][0]["message"].get("content", "")
        return f"> *Processamento avançado executado via R1.*\\n\\n{content}" if reasoning and target_model == "deepseek-reasoner" else content.strip()
    except Exception as e:
        return f"❌ Erro na Comunicação com a API: {str(e)}"

# ================= RENDERIZAÇÃO GERAL =================

st.markdown('''
<style>
:root { --amoled:#080d10; --bubble-ai:#172229; --bubble-user:#075e54; --border:#263840; --text:#e9edef; --muted:#8696a0; --green:#00a884; }
.stApp { background: radial-gradient(circle at 50% 10%, rgba(0,168,132,.08), transparent 35%), linear-gradient(180deg,#080d10,#0b141a) !important; color:var(--text) !important; }
[data-testid="stHeader"] { background:transparent !important; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#0e171c,#0b141a) !important; border-right:1px solid var(--border) !important; }
.login-box { max-width:400px; margin: 100px auto; padding:40px 30px; background:linear-gradient(145deg,#121d23,#0c1419); border:1px solid var(--border); border-radius:24px; box-shadow:0 25px 80px rgba(0,0,0,.45); text-align:center; }
.rog-mark { width:64px; height:64px; margin:0 auto 16px; display:flex; align-items:center; justify-content:center; border-radius:18px; background:linear-gradient(145deg,#123d35,#0d211d); border:1px solid rgba(0,168,132,.45); color:#36d9b3; font-size:28px; font-weight:800; }
.chat-header { min-height:70px; display:flex; align-items:center; gap:13px; background:rgba(17,28,34,.92); border:1px solid var(--border); border-radius:15px; padding:10px 16px; margin-bottom:13px; backdrop-filter:blur(10px); }
.chat-avatar { width:46px; height:46px; display:flex; align-items:center; justify-content:center; background:linear-gradient(145deg,#1a2a31,#0d171c); border:1px solid #344750; border-radius:14px; font-size:23px; }
.chat-agent-name { color:var(--text); font-size:18px; font-weight:700; }
.chat-agent-desc { color:var(--muted); font-size:12px; margin-top:3px; }
.message-user,.message-ai { display:flex; width:100%; margin:10px 0; }
.message-user { justify-content:flex-end; }
.message-ai { justify-content:flex-start; }
.bubble-user { max-width:80%; background:linear-gradient(145deg,#075e54,#075449); border:1px solid #0a806f; border-radius:14px 4px 14px 14px; padding:12px 16px; font-size:16px; line-height: 1.5; box-shadow:0 2px 7px rgba(0,0,0,.18); }
.bubble-ai { max-width:84%; background:linear-gradient(145deg,#172229,#152027); border:1px solid var(--border); border-radius:4px 14px 14px 14px; padding:12px 18px; font-size:16px; line-height: 1.6; box-shadow:0 2px 7px rgba(0,0,0,.18); }
.bubble-ai p, .bubble-user p, .bubble-ai li { font-size: 16px !important; }
.message-time { color:rgba(233,237,239,.48); font-size:10px; text-align:right; margin-top:6px; }
[data-testid="stSidebar"] button { border-radius:10px !important; border:1px solid transparent !important; background:transparent !important; color:var(--text) !important; text-align:left !important; padding:8px 12px !important; transition:0.2s; }
[data-testid="stSidebar"] button:hover { background:#17232a !important; border-color:var(--border) !important; }
[data-testid="stSidebar"] button[kind="primary"] { background:rgba(0,168,132,.12) !important; border-left:3px solid var(--green) !important; }
</style>
''', unsafe_allow_html=True)

if not st.session_state.authenticated:
    st.markdown('''
    <div class="login-box">
        <div class="rog-mark">R</div>
        <div style="font-size:24px; font-weight:bold; margin-bottom:5px;">ROG AI</div>
        <div style="font-size:12px; color:#8696a0; margin-bottom:20px;">Acesso Criptografado</div>
    ''', unsafe_allow_html=True)
    
    profile_choice = st.selectbox("Selecione sua conta", ["Allan", "Beatriz", "Natan", "Tainan"])
    input_pass = st.text_input("Senha", type="password")
    lembrar_me = st.checkbox("Manter logado (Favoritar URL)")
    
    if st.button("Autenticar", use_container_width=True, type="primary"):
        if input_pass == PASSWORDS[profile_choice]:
            st.session_state.authenticated = True
            st.session_state.current_profile = profile_choice
            if lembrar_me:
                st.query_params["auth"] = hashlib.md5(input_pass.encode()).hexdigest()
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.markdown('</div>', unsafe_allow_html=True)
    
else:
    current_profile = st.session_state.current_profile
    if "conversations" not in st.session_state:
        st.session_state.conversations = st.session_state.long_memory[current_profile].get("history", {a_id: [] for a_id in AGENTS})
    
    with st.sidebar:
        st.markdown(f'''
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:20px;">
                <div class="rog-mark" style="width:36px; height:36px; font-size:16px; margin:0;">R</div>
                <div><div style="font-weight:bold; font-size:18px;">ROG AI</div><div style="font-size:11px; color:#00a884;">● {current_profile} Online</div></div>
            </div>
            <hr style="border-color:#263840; margin:10px 0;">
        ''', unsafe_allow_html=True)
        
        for a_id, a_data in AGENTS.items():
            sel = (st.session_state.current_agent == a_id)
            if st.button(f"{a_data['icon']}  {a_data['name']}", key=f"agent_{a_id}", use_container_width=True, type="primary" if sel else "secondary"):
                if not sel: st.session_state.current_agent = a_id; st.rerun()
                
        st.markdown('<hr style="border-color:#263840; margin:15px 0;">', unsafe_allow_html=True)
        if st.button("↪ Encerrar Sessão", use_container_width=True):
            st.query_params.clear()
            st.session_state.authenticated = False
            st.session_state.current_profile = None
            st.rerun()

    agent_id = st.session_state.current_agent
    agent = AGENTS[agent_id]
    
    st.markdown(f'''
    <div class="chat-header">
        <div class="chat-avatar">{agent["icon"]}</div>
        <div><div class="chat-agent-name">{agent["name"]}</div><div class="chat-agent-desc">{agent["description"]}</div></div>
    </div>
    ''', unsafe_allow_html=True)

    history = st.session_state.conversations.get(agent_id, [])
    for msg in history:
        if msg["role"] == "user":
            st.markdown(f'<div class="message-user"><div class="bubble-user">{html.escape(msg["content"])}<div class="message-time">{msg.get("time", "")}</div></div></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="message-ai"><div class="bubble-ai"><div style="color:#00a884; font-size:11px; font-weight:bold; margin-bottom:6px;">{msg.get("agent", {}).get("icon", "🤖")} {msg.get("agent", {}).get("name", "ROG AI")}</div>{msg["content"]}<div class="message-time">{msg.get("time", "")}</div></div></div>', unsafe_allow_html=True)

    # Painel de Anexo de Imagem (OCR Real) integrando com o Chat Nativo
    uploaded_image = st.file_uploader("📎 Anexar imagem para leitura óptica (OCR)", type=["png", "jpg", "jpeg"])
    user_input = st.chat_input(f"Mensagem para {agent['name']}...")

    if user_input or uploaded_image:
        img_b64 = None
        display_text = user_input if user_input else "Analise esta imagem."
        
        if uploaded_image:
            bytes_data = uploaded_image.getvalue()
            img_b64 = base64.b64encode(bytes_data).decode('utf-8')
            display_text = f"[Imagem Anexada] {display_text}"

        st.session_state.conversations[agent_id].append({"role": "user", "content": display_text, "time": time.strftime("%H:%M"), "agent": agent, "img": img_b64})
        st.session_state.long_memory[current_profile]["history"] = st.session_state.conversations
        save_long_term_memory(st.session_state.long_memory)
        st.rerun()

    if len(history) > 0 and history[-1]["role"] == "user":
        last_msg = history[-1]
        with st.spinner(f"Aguarde, {agent['name']} está processando a solicitação e imagem..."):
            ans = ask_deepseek(agent_id, history[:-1], last_msg["content"], last_msg.get("img"))
            st.session_state.conversations[agent_id].append({"role": "assistant", "content": ans, "time": time.strftime("%H:%M"), "agent": agent})
            st.session_state.long_memory[current_profile]["history"] = st.session_state.conversations
            save_long_term_memory(st.session_state.long_memory)
            st.rerun()