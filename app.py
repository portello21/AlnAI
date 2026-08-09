import streamlit as st
import requests

# Configuração da página
st.set_page_config(
    page_title="Allan AI",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS limpa e funcional
st.markdown("""
    <style>
    /* Ocultar cabeçalhos e rodapés do Streamlit */
    [data-testid="stHeader"], footer, #MainMenu { display: none !important; }
    
    /* Preenchimento principal */
    .main .block-container { 
        padding-top: 1.5rem !important; 
        padding-bottom: 2rem !important;
        max-width: 1000px !important;
        margin: 0 auto !important;
    }
    
    /* Fundo Escuro */
    .stApp { 
        background-color: #0b141a !important; 
        color: #e9edef !important; 
    }
    
    /* Barra Lateral */
    section[data-testid="stSidebar"] { 
        background-color: #111b21 !important; 
        border-right: 1px solid #222d34 !important; 
    }
    
    /* Balões de Mensagem */
    div[data-testid="stChatMessage"] {
        background-color: #202c33 !important;
        border-radius: 12px !important;
        padding: 12px 16px !important;
        margin-bottom: 12px !important;
        border: 1px solid #2a3942 !important;
    }
    
    /* Campo de Entrada */
    div[data-testid="stChatInput"] {
        border-radius: 12px !important;
    }
    div[data-testid="stChatInput"] > div {
        background-color: #202c33 !important;
        border: 1px solid #2a3942 !important;
        border-radius: 12px !important;
    }
    
    /* Ajustes na Sidebar */
    section[data-testid="stSidebar"] .stRadio > label { display: none; }
    </style>
""", unsafe_allow_html=True)

# Definição dos Agentes
AGENTS = {
    "🤖 Orquestrador (Auto)": {
        "desc": "Triagem e roteamento dinâmico da malha.",
        "avatar": "🤖",
        "system": "Você é o ORQUESTRADOR PRINCIPAL do Allan AI. Moeda padrão: CAD ($). Cidade: Hamilton/Ontario. Respondas de forma direta e objetiva."
    },
    "👤 Personal Agent": {
        "desc": "Gestão de tempo, rotina e logística.",
        "avatar": "👤",
        "system": "Você é o PERSONAL AGENT. Especialista em gestão de tempo, agenda e rotina pessoal em Hamilton, Ontario."
    },
    "💰 Finance Agent": {
        "desc": "Contabilidade, extratos e saldos em CAD ($).",
        "avatar": "💰",
        "system": "Você é o FINANCE AGENT. Mantenha os lançamentos e cálculos estritamente em CAD ($). Estrutura: Lançamentos | Totais | Saldo Final Líquido."
    },
    "💻 Tech Agent": {
        "desc": "Scripts PowerShell, Docker e engenharia de software.",
        "avatar": "💻",
        "system": "Você é o TECH AGENT. Forneça scripts limpos em PowerShell, automações e comandos Docker prontos para uso."
    },
    "🏋️ Coach Agent": {
        "desc": "Treinos hipertróficos e metas hiperproteicas.",
        "avatar": "🏋️",
        "system": "Você é o COACH AGENT. Prescreva treinos focados em hipertrofia (RIR/RPE) e dietas de alta proteína em g/kg."
    },
    "💼 Business Agent": {
        "desc": "Precificação e contratos operacionais em CAD ($).",
        "avatar": "💼",
        "system": "Você é o BUSINESS AGENT. Calcule margem de lucro, insumos e taxas operacionais por hora em CAD ($)."
    },
    "🇺🇸 English Teacher": {
        "desc": "Tradução, correções e treino de conversação.",
        "avatar": "🇺🇸",
        "system": "Você é o ENGLISH AGENT. Traduza com vocabulário natural do Canadá, corrija erros do usuário e explique regras gramaticais em português."
    }
}

# Sidebar - Seleção de Agente
st.sidebar.markdown("## 💬 Allan AI")
st.sidebar.caption("Conversas ativas:")

selected_agent_name = st.sidebar.radio("Selecione o agente:", list(AGENTS.keys()), label_visibility="collapsed")
current_agent = AGENTS[selected_agent_name]

if "messages" not in st.session_state:
    st.session_state.messages = {agent: [] for agent in AGENTS.keys()}

# Cabeçalho do Chat Selecionado
col_avatar, col_title = st.columns([0.08, 0.92])
with col_avatar:
    st.title(current_agent["avatar"])
with col_title:
    st.subheader(selected_agent_name)
    st.caption(current_agent["desc"])

st.divider()

# Histórico de Mensagens
for msg in st.session_state.messages[selected_agent_name]:
    avatar = "🟢" if msg["role"] == "user" else current_agent["avatar"]
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])

# Entrada do Usuário
if prompt := st.chat_input("Digite sua mensagem..."):
    st.session_state.messages[selected_agent_name].append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🟢"):
        st.write(prompt)

    with st.chat_message("assistant", avatar=current_agent["avatar"]):
        with st.spinner("Pensando na nuvem..."):
            api_key = st.secrets.get("DEEPSEEK_API_KEY", "")
            if not api_key:
                response_text = "Erro: Chave DEEPSEEK_API_KEY não encontrada nos Secrets do Streamlit."
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
                    response_text = f"Erro de conexão: {e}"

            st.write(response_text)
            st.session_state.messages[selected_agent_name].append({"role": "assistant", "content": response_text})