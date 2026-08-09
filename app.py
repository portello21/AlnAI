import streamlit as st
import requests

st.set_page_config(page_title="Allan AI", page_icon="💬", layout="wide", initial_sidebar_state="expanded")

# Injeção CSS para visual limpo
st.markdown("""
    <style>
    [data-testid="stHeader"], footer, #MainMenu { display: none !important; }
    .block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; }
    .stApp { background-color: #0b141a !important; color: #e9edef !important; }
    section[data-testid="stSidebar"] { background-color: #111b21 !important; border-right: 1px solid #222d34 !important; }
    div[data-testid="stChatInput"] { background-color: #202c33 !important; border: 1px solid #2a3942 !important; border-radius: 8px !important; }
    </style>
""", unsafe_allow_html=True)

# Definição dos Agentes e Instruções
AGENTS = {
    "🤖 Orquestrador (Auto)": {
        "desc": "Triagem e roteamento geral da malha de agentes.",
        "avatar": "🤖",
        "system": "Você é o ORQUESTRADOR PRINCIPAL do Allan AI. Moeda padrão: CAD ($). Cidade: Hamilton/Ontario. Delegue ou responda direto com objetividade."
    },
    "👤 Personal Agent": {
        "desc": "Gestão de tempo, rotina e logística.",
        "avatar": "👤",
        "system": "Você é o PERSONAL AGENT. Especialista em gestão de tempo e rotina em Hamilton, Ontario."
    },
    "💰 Finance Agent": {
        "desc": "Contabilidade, extratos e saldos em CAD ($).",
        "avatar": "💰",
        "system": "Você é o FINANCE AGENT. Todas as operações devem ser em Dólar Canadense (CAD / $). Estrutura: Lançamentos | Totais | Saldo Final Líquido."
    },
    "💻 Tech Agent": {
        "desc": "Scripts PowerShell, Docker e engenharia de software.",
        "avatar": "💻",
        "system": "Você é o TECH AGENT. Forneça scripts limpos em PowerShell e comandos Docker operacionais."
    },
    "🏋️ Coach Agent": {
        "desc": "Treinos hipertróficos e metas hiperproteicas.",
        "avatar": "🏋️",
        "system": "Você é o COACH AGENT. Foco em musculação (hipertrofia, RIR/RPE) e dietas de alta proteína em g/kg."
    },
    "💼 Business Agent": {
        "desc": "Precificação e contratos operacionais em CAD ($).",
        "avatar": "💼",
        "system": "Você é o BUSINESS AGENT. Precificação de serviços, margem de lucro e taxas por hora em CAD ($)."
    },
    "🇺🇸 English Teacher": {
        "desc": "Tradução, correções e treino de conversação.",
        "avatar": "🇺🇸",
        "system": "Você é o ENGLISH AGENT. Traduza com vocabulário canadense natural, corrija frases e explique regras gramaticais em português."
    }
}

st.sidebar.title("💬 Allan AI")
st.sidebar.caption("Conversas ativas:")

selected_agent_name = st.sidebar.radio("Selecione a conversa:", list(AGENTS.keys()), label_visibility="collapsed")
current_agent = AGENTS[selected_agent_name]

if "messages" not in st.session_state:
    st.session_state.messages = {agent: [] for agent in AGENTS.keys()}

col1, col2 = st.columns([0.08, 0.92])
with col1:
    st.title(current_agent["avatar"])
with col2:
    st.subheader(selected_agent_name)
    st.caption(current_agent["desc"])

st.divider()

for msg in st.session_state.messages[selected_agent_name]:
    avatar = "🟢" if msg["role"] == "user" else current_agent["avatar"]
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])

if prompt := st.chat_input("Digite sua mensagem..."):
    st.session_state.messages[selected_agent_name].append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🟢"):
        st.write(prompt)

    with st.chat_message("assistant", avatar=current_agent["avatar"]):
        with st.spinner("Pensando na nuvem..."):
            api_key = st.secrets.get("DEEPSEEK_API_KEY", "")
            if not api_key:
                response_text = "Erro: Chave DEEPSEEK_API_KEY não configurada nos Secrets do Streamlit."
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
                    response_text = f"Erro de Conexão: {e}"

            st.write(response_text)
            st.session_state.messages[selected_agent_name].append({"role": "assistant", "content": response_text})