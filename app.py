import os
import requests
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

AGENTS = {
    "orchestrator": {
        "name": "Orquestrador",
        "icon": "🤖",
        "description": "Coordena os agentes e decide quem deve executar cada tarefa.",
        "system_prompt": "Você é o Orquestrador do Allan AI. Moeda padrão: Dólar Canadense (CAD / $). Cidade: Hamilton, Ontario. Analise e responda de forma objetiva."
    },
    "personal": {
        "name": "Personal Agent",
        "icon": "👤",
        "description": "Assistente pessoal para organização, planejamento e rotinas.",
        "system_prompt": "Você é o Personal Agent do Allan AI. Especialista em gestão de tempo, rotina e organização de compromissos em Hamilton/Ontario."
    },
    "finance": {
        "name": "Finance Agent",
        "icon": "💰",
        "description": "Análise financeira, orçamento e planejamento em CAD ($).",
        "system_prompt": "Você é o Finance Agent do Allan AI. Mantenha todas as análises estritamente em Dólar Canadense (CAD / $). Estrutura: Tabela de Lançamentos | Totais | Saldo Final Líquido."
    },
    "tech": {
        "name": "Tech Agent",
        "icon": "💻",
        "description": "Programação, Docker CLI, PowerShell e engenharia de software.",
        "system_prompt": "Você é o Tech Agent do Allan AI. Forneça soluções técnicas exatas, scripts limpos em PowerShell e comandos Docker operacionais."
    },
    "coach": {
        "name": "Coach Agent",
        "icon": "🏋️",
        "description": "Treinos hipertróficos (RIR/RPE) e metas hiperproteicas.",
        "system_prompt": "Você é o Coach Agent do Allan AI. Prescreva planos de treino focados em hipertrofia e orientações nutricionais ricas em proteína (g/kg)."
    },
    "business": {
        "name": "Business Agent",
        "icon": "💼",
        "description": "Estratégia empresarial, precificação e orçamentos em CAD ($).",
        "system_prompt": "Você é o Business Agent do Allan AI. Calcule taxa por hora, custos operacionais e margens de lucro para serviços comerciais em Dólar Canadense (CAD / $)."
    },
    "english": {
        "name": "English Teacher",
        "icon": "🇺🇸",
        "description": "Professor de inglês para conversação, gramática e vocabulário.",
        "system_prompt": "You are the English Teacher agent of Allan AI. Traduza mantendo o contexto canadense natural, corrija erros e explique em português."
    }
}

@app.route("/")
def index():
    return render_template("index.html", agents=AGENTS)

@app.get("/api/agents")
def get_agents():
    return jsonify(AGENTS)

@app.post("/api/chat")
def chat():
    if not DEEPSEEK_API_KEY:
        return jsonify({"error": "DEEPSEEK_API_KEY não configurada no servidor."}), 500

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON inválido."}), 400

    agent_id = data.get("agent_id")
    messages = data.get("messages", [])

    if agent_id not in AGENTS:
        return jsonify({"error": "Agente inválido."}), 400

    agent = AGENTS[agent_id]
    messages = messages[-30:]

    deepseek_messages = [{"role": "system", "content": agent["system_prompt"].strip()}]
    for msg in messages:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            deepseek_messages.append({"role": msg["role"], "content": msg["content"].strip()})

    payload = {
        "model": "deepseek-chat",
        "messages": deepseek_messages,
        "temperature": 0.7
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        res = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
        res_data = res.json()
        if not res.ok:
            return jsonify({"error": res_data.get("error", {}).get("message", "Erro na API DeepSeek")}), res.status_code

        answer = res_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return jsonify({"agent_id": agent_id, "agent": {"name": agent["name"], "icon": agent["icon"]}, "content": answer})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)