import streamlit as st
import requests
import streamlit.components.v1 as components

# Configuração da página
st.set_page_config(
    page_title="Allan AI",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS inspirada no Telegram / WhatsApp Dark
st.markdown("""
    <style>
    /* Ocultar elementos padrão */
    [data-testid="stHeader"], footer, #MainMenu { display: none !important; }
    
    /* Fundo escuro AMOLED/OLED */
    .stApp {
        background-color: #0b141a !important;
        color: #e9edef !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }
    
    /* Container central do chat */
    .main .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 3rem !important;
        max-width: 900px !important;
        margin: 0 auto !important;
    }
    
    /* Barra Lateral - Lista de Agentes */
    section[data-testid="stSidebar"] {
        background-color: #111b21 !important;
        border-right: 1px solid #222d34 !important;
    }
    
    /* Botões da Sidebar estilo Telegram */
    div[data-testid="stRadio"] div[role="radiogroup"] > label {
        background-color: #111b21 !important;
        color: #e9edef !important;
        border: 1px solid #222d34 !important;
        border-radius: 10px !important;
        padding: 10px 14px !important;
        margin-bottom: 6px !important;
        transition: all 0.2s ease-in-out !important;
        cursor: pointer !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] > label:hover {
        background-color: #202c33 !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] > label[data-checked="true"] {
        background-color: #2a3942 !important;
        border-color: #00a884 !important;
        font-weight: 600 !important;
    }

    /* Balões de Mensagem */
    div[data-testid="stChatMessage"] {
        background-color: #202c33 !important;
        border-radius: 14px !important;
        padding: 12px 16px !important;
        margin-bottom: 12px !important;
        border: 1px solid #2a3942 !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
    }
    
    /* Destaque para mensagem do Usuário */
    div[data-testid="stChatMessage"]:has(div:contains("🟢")) {
        background-color: #005c4b !important;
        border-color: #008069 !important;
    }
    
    /* Caixa de entrada */
    div[data-testid="stChatInput"] {
        border-radius: 20px !important;
    }
    div[data-testid="stChatInput"] > div {
        background-color: #202c33 !important;
        border: 1px solid #2a3942 !important;
        border-radius: 20px !important;
    }
    div[data-testid="stChatInput"] textarea {
        color: #e9edef !important;
    }
    
    hr { border-color: #222d34 !important; }
    </style>
""", unsafe_allow_html=True)

# Definição dos Agentes do Allan AI
AGENTS = {
    "🤖 Orquestrador (Auto)": {
        "desc": "Triagem e roteamento inteligente para toda a malha.",
        "avatar": "🤖",
        "system": "Você é o ORQUESTRADOR PRINCIPAL do Allan AI. Moeda padrão: Dólar Canadense (CAD / $). Cidade de referência: Hamilton, Ontario, Canadá. Responda com clareza, objetividade e sem enrolação."
    },
    "👤 Personal Agent": {
        "desc": "Gestão de tempo, rotina diária e logística pessoal.",
        "avatar": "👤",
        "system": "Você é o PERSONAL AGENT do Allan AI. Especialista em gestão de tempo, rotina e organização de compromissos locais em Hamilton/Ontario."
    },
    "💰 Finance Agent": {
        "desc": "Análise contábil, extratos e controle financeiro em CAD ($).",
        "avatar": "💰",
        "system": "Você é o FINANCE AGENT do Allan AI. Mantenha todas as análises e saldos estritamente em Dólar Canadense (CAD / $). Estrutura exigida: Tabela de Lançamentos | Totais (Entradas vs Saídas) | Saldo Final Líquido."
    },
    "💻 Tech Agent": {
        "desc": "Scripts PowerShell, Docker CLI e suporte a hardware.",
        "avatar": "💻",
        "system": "Você é o TECH AGENT do Allan AI. Entregue soluções técnicas exatas, scripts limpos em PowerShell e comandos Docker operacionais."
    },
    "🏋️ Coach Agent": {
        "desc": "Treinos de musculação (hipertrofia) e metas hiperproteicas.",
        "avatar": "🏋️",
        "system": "Você é o COACH AGENT do Allan AI. Prescreva planos de treino focados em hipertrofia (com indicação de volume e RIR/RPE) e orientações nutricionais ricas em proteína (g/kg)."
    },
    "💼 Business Agent": {
        "desc": "Precificação de serviços, margem de lucro e orçamentos em CAD ($).",
        "avatar": "💼",
        "system": "Você é o BUSINESS AGENT do Allan AI. Calcule taxa por hora, custos operacionais e margens de lucro para serviços comerciais em Dólar Canadense (CAD / $)."
    },
    "🇺🇸 English Teacher": {
        "desc": "Professor de inglês: tradução contextual, correções e fluência.",
        "avatar": "🇺🇸",
        "system": "Você é o ENGLISH AGENT (English Teacher & Translator). Traduza frases mantendo o contexto canadense natural, corrija erros gramaticais e ofereça explicações em português de forma simples."
    }
}

# Sidebar UI
st.sidebar.markdown("## 💬 Allan AI")
st.sidebar.caption("Conversas ativas:")

selected_agent_name = st.sidebar.radio("Selecione a conversa:", list(AGENTS.keys()), label_visibility="collapsed")
current_agent = AGENTS[selected_agent_name]

if "messages" not in st.session_state:
    st.session_state.messages = {agent: [] for agent in AGENTS.keys()}

# Cabeçalho do Chat
col_avatar, col_info = st.columns([0.1, 0.9])
with col_avatar:
    st.title(current_agent["avatar"])
with col_info:
    st.markdown(f"### {selected_agent_name}")
    st.caption(current_agent["desc"])

st.divider()

# Exibir Mensagens Salvas
for msg in st.session_state.messages[selected_agent_name]:
    avatar_icon = "🟢" if msg["role"] == "user" else current_agent["avatar"]
    with st.chat_message(msg["role"], avatar=avatar_icon):
        st.write(msg["content"])

# Processar Envio de Mensagens
if prompt := st.chat_input("Digite sua mensagem..."):
    st.session_state.messages[selected_agent_name].append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🟢"):
        st.write(prompt)

    with st.chat_message("assistant", avatar=current_agent["avatar"]):
        with st.spinner("Pensando na nuvem..."):
            api_key = st.secrets.get("DEEPSEEK_API_KEY", "")
            if not api_key:
                response_text = "⚠️ Erro: A chave DEEPSEEK_API_KEY não está configurada nos Secrets do Streamlit Cloud."
            else:
                try:
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": current_agent["system"]},
                            {"role": "user", "content": prompt}
                        ]
                    }
                    res = requests.post("https://api.deepseek.com/v1/chat/completions", json=payload, headers=headers, timeout=60)
                    if res.status_code == 200:
                        response_text = res.json()["choices"][0]["message"]["content"]
                    else:
                        response_text = f"Erro na API DeepSeek ({res.status_code}): {res.text}"
                except Exception as e:
                    response_text = f"Erro de conexão com o servidor: {e}"

            st.write(response_text)
            st.session_state.messages[selected_agent_name].append({"role": "assistant", "content": response_text})

            # Injeção de áudio automático para leitura da resposta em voz alta
            lang_code = "en-US" if selected_agent_name == "🇺🇸 English Teacher" else "pt-BR"
            clean_speech = response_text.replace("", "").replace("*", "").replace("#", "")
            tts_script = f"""
            <script>
            if ('speechSynthesis' in window) {{
                window.speechSynthesis.cancel();
                var msg = new SpeechSynthesisUtterance({repr(clean_speech)});
                msg.lang = '{lang_code}';
                msg.rate = 1.0;
                window.speechSynthesis.speak(msg);
            }}
            </script>
            """
            components.html(tts_script, height=0)