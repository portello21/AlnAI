from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.llm_router import chat as llm_chat, chat_with_metadata, local_available
from core.model_policy import IntelligentModelRouter
from core.skills_loader import build_agent_skills_context
from core.memory_engine import MemoryEngine
from core.memory_context import MemoryContextBuilder


_memory_engine = MemoryEngine()
_memory_context_builder = MemoryContextBuilder(max_memories=6, max_chars=4000)


def build_memory_context(
    profile: Optional[str],
    user_query: str,
    retrieval_limit: int = 12,
    max_memories: int = 6,
    max_chars: int = 4000,
) -> dict:

    empty = {
        "text": "",
        "retrieved_count": 0,
        "retrieved_ids": [],
        "context_count": 0,
        "context_ids": [],
        "context_chars": 0,
        "context_truncated": False,
        "budget_chars": max_chars,
        "memories": [],
    }

    if not profile:
        return empty

    try:

        memories = _memory_engine.search_memories(
            profile=profile,
            query=user_query,
            limit=max(
                retrieval_limit,
                max_memories,
            ),
        )

    except Exception:

        return empty

    retrieved_ids = [
        memory.get("id")
        for memory in memories
        if memory.get("id")
    ]

    built = _memory_context_builder.build(
        memories=memories,
        max_memories=max_memories,
        max_chars=max_chars,
    )

    return {
        "text": built.get(
            "text",
            "",
        ),
        "retrieved_count": len(
            memories
        ),
        "retrieved_ids": retrieved_ids,
        "context_count": built.get(
            "memory_count",
            0,
        ),
        "context_ids": built.get(
            "memory_ids",
            [],
        ),
        "context_chars": built.get(
            "characters",
            0,
        ),
        "context_truncated": built.get(
            "truncated",
            False,
        ),
        "budget_chars": built.get(
            "budget_chars",
            max_chars,
        ),
        "memories": built.get(
            "memories",
            [],
        ),
    }




_model_router = IntelligentModelRouter()


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    name: str
    model: str
    instruction: str


AGENTS = {
    "orchestrator": AgentSpec(
        agent_id="orchestrator",
        name="ROG AI Core",
        model="deepseek-chat",
        instruction=(
            "Voce e o ROG AI Core, o orquestrador principal. "
            "Entenda a solicitacao do usuario e responda diretamente "
            "quando nenhuma especialidade for necessaria."
        ),
    ),

    "personal": AgentSpec(
        agent_id="personal",
        name="Personal Agent",
        model="deepseek-chat",
        instruction=(
            "Atue em organizacao pessoal, rotina, agenda, "
            "planejamento e logistica."
        ),
    ),

    "finance": AgentSpec(
        agent_id="finance",
        name="Finance Agent",
        model="deepseek-reasoner",
        instruction=(
            "Atue em financas, orcamento, receitas, despesas, "
            "fluxo de caixa, projecoes e planejamento financeiro."
        ),
    ),

    "tech": AgentSpec(
        agent_id="tech",
        name="Tech Agent",
        model="deepseek-reasoner",
        instruction=(
            "Atue em programacao, Python, PowerShell, Docker, APIs, "
            "hardware, software, infraestrutura e arquitetura de sistemas."
        ),
    ),

    "coach": AgentSpec(
        agent_id="coach",
        name="Coach Agent",
        model="deepseek-chat",
        instruction=(
            "Atue em treinamento fisico, exercicios, biomecanica, "
            "recuperacao e planejamento nutricional esportivo."
        ),
    ),

    "business": AgentSpec(
        agent_id="business",
        name="Business Agent",
        model="deepseek-reasoner",
        instruction=(
            "Atue em negocios, estrategia, custos, margem, "
            "precificacao e geracao de receita."
        ),
    ),

    "english": AgentSpec(
        agent_id="english",
        name="English Teacher",
        model="deepseek-chat",
        instruction=(
            "Atue como professor de ingles e tradutor. "
            "Ajude com conversacao, vocabulario, gramatica e pronuncia."
        ),
    ),

    "document": AgentSpec(
        agent_id="document",
        name="Document Agent",
        model="qwen3",
        instruction=(
            "Atue em leitura, analise, resumo, extracao e "
            "interpretacao de documentos e arquivos."
        ),
    ),
}


ROUTING_SYSTEM_PROMPT = """
Voce e o roteador interno do ROG AI.

Classifique a solicitacao do usuario em EXATAMENTE uma categoria:

personal
finance
tech
coach
business
english
document
orchestrator

Regras:

personal = rotina, agenda, organizacao pessoal e logistica.
finance = dinheiro, contas, despesas, receitas, orcamento e projecoes.
tech = programacao, computadores, software, hardware, APIs e sistemas.
coach = treino, exercicios, biomecanica e nutricao esportiva.
business = negocios, vendas, precificacao, margem e receita.
english = ingles, traducao, vocabulario, gramatica e conversacao.
document = documentos, arquivos, PDFs, OCR, extracao e resumo.
orchestrator = perguntas gerais que nao exigem especialista.

Retorne SOMENTE o nome da categoria.
"""


def normalize_agent_id(value: str) -> str:
    value = (value or "").strip().lower()

    aliases = {
        "root": "orchestrator",
        "personal_agent": "personal",
        "finance_agent": "finance",
        "tech_agent": "tech",
        "coach_agent": "coach",
        "business_agent": "business",
        "english_agent": "english",
        "document_agent": "document",
    }

    return aliases.get(value, value)


def route_query(user_query: str) -> str:
    messages = [
        {
            "role": "system",
            "content": ROUTING_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_query,
        },
    ]

    try:
        result = llm_chat(
            model="deepseek-chat",
            messages=messages,
            temperature=0,
            max_tokens=32,
        )

        routed = normalize_agent_id(result)

        if routed in AGENTS:
            return routed

    except Exception:
        pass

    return "orchestrator"


def build_messages(
    agent_id: str,
    history: list,
    user_query: str,
    extra_context: Optional[str] = None,
) -> list:

    agent_id = normalize_agent_id(agent_id)

    if agent_id not in AGENTS:
        agent_id = "orchestrator"

    agent = AGENTS[agent_id]

    system_content = (
        f"Voce e o agente especialista: {agent.name}.\n"
        f"Instrucao primaria: {agent.instruction}\n"
        "Responda em Markdown limpo.\n"
        "Nao invente dados ausentes."
    )

    skills_context = build_agent_skills_context(agent_id)

    if skills_context:
        system_content += "\n\n" + skills_context

    if extra_context:
        system_content += (
            "\n\nCONTEXTO ADICIONAL:\n"
            + extra_context
        )

    messages = [
        {
            "role": "system",
            "content": system_content,
        }
    ]

    for item in history[-20:]:
        role = item.get("role")
        content = item.get("content")

        if role in {"user", "assistant"} and content:
            messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

    messages.append(
        {
            "role": "user",
            "content": user_query,
        }
    )

    return messages


def execute_agent(
    agent_id: str,
    history: list,
    user_query: str,
    extra_context: Optional[str] = None,
    profile: Optional[str] = None,
) -> dict:

    requested_agent = normalize_agent_id(
        agent_id
    )

    if requested_agent not in AGENTS:
        requested_agent = "orchestrator"


    # ========================================================
    # AGENT ROUTING
    # ========================================================

    if requested_agent == "orchestrator":

        selected_agent = route_query(
            user_query
        )

    else:

        selected_agent = requested_agent


    agent = AGENTS[
        selected_agent
    ]


    # ========================================================
    # MEMORY V3.2
    # ========================================================

    memory_result = build_memory_context(
        profile=profile,
        user_query=user_query,
        retrieval_limit=12,
        max_memories=6,
        max_chars=4000,
    )

    memory_context = memory_result[
        "text"
    ]


    # ========================================================
    # CONTEXT
    # ========================================================

    combined_context_parts = []

    if extra_context:

        combined_context_parts.append(
            extra_context
        )

    if memory_context:

        combined_context_parts.append(
            memory_context
        )

    combined_context = (
        "\n\n".join(
            combined_context_parts
        )
        if combined_context_parts
        else None
    )


    # ========================================================
    # PROMPT
    # ========================================================

    messages = build_messages(
        agent_id=selected_agent,
        history=history,
        user_query=user_query,
        extra_context=combined_context,
    )


    # ========================================================
    # INTELLIGENT MODEL ROUTER V2
    # ========================================================

    try:

        local_is_available = bool(
            local_available()
        )

    except Exception:

        local_is_available = False


    routing_decision = (
        _model_router.decide(
            agent_id=selected_agent,
            user_query=user_query,
            requested_model=agent.model,
            local_available=
                local_is_available,
        )
    )


    selected_model = (
        routing_decision.selected_model
    )


    # ========================================================
    # MODEL BUDGET
    # ========================================================

    max_tokens = (
        2048
        if "qwen3"
        in selected_model.lower()
        else 4096
    )


    # ========================================================
    # LLM EXECUTION
    # ========================================================

    llm_result = chat_with_metadata(
        model=selected_model,
        messages=messages,
        temperature=0.2,
        max_tokens=max_tokens,
    )


    # ========================================================
    # MEMORY USAGE
    #
    # Somente memorias que realmente entraram no prompt
    # e somente se a execucao foi considerada bem sucedida.
    # ========================================================

    if llm_result.get(
        "success",
        True,
    ):

        for memory_id in memory_result[
            "context_ids"
        ]:

            try:

                _memory_engine.mark_used(
                    memory_id
                )

            except Exception:

                pass


    # ========================================================
    # RESULT / OBSERVABILITY
    # ========================================================

    return {
        "requested_agent":
            requested_agent,

        "selected_agent":
            selected_agent,

        "agent_name":
            agent.name,

        "profile":
            profile,


        # ----------------------------------------------------
        # MEMORY compatibility
        # ----------------------------------------------------

        "memory_count":
            memory_result[
                "context_count"
            ],

        "memory_ids":
            memory_result[
                "context_ids"
            ],


        # ----------------------------------------------------
        # MEMORY V3.2
        # ----------------------------------------------------

        "memory_retrieved_count":
            memory_result[
                "retrieved_count"
            ],

        "memory_retrieved_ids":
            memory_result[
                "retrieved_ids"
            ],

        "memory_context_count":
            memory_result[
                "context_count"
            ],

        "memory_context_ids":
            memory_result[
                "context_ids"
            ],

        "memory_context_chars":
            memory_result[
                "context_chars"
            ],

        "memory_context_budget":
            memory_result[
                "budget_chars"
            ],

        "memory_context_truncated":
            memory_result[
                "context_truncated"
            ],


        # ----------------------------------------------------
        # MODEL ROUTER V2
        # ----------------------------------------------------

        "agent_default_model":
            agent.model,

        "requested_model":
            routing_decision.requested_model,

        "selected_model":
            selected_model,

        "route_mode":
            routing_decision.route_mode,

        "route_reason":
            routing_decision.reason,

        "complexity_score":
            routing_decision.complexity_score,

        "reasoning_score":
            routing_decision.reasoning_score,

        "privacy_score":
            routing_decision.privacy_score,

        "local_available":
            routing_decision.local_available,


        # ----------------------------------------------------
        # ACTUAL EXECUTION
        # ----------------------------------------------------

        "model":
            llm_result.get(
                "model",
                selected_model,
            ),

        "provider":
            llm_result.get(
                "provider",
                "unknown",
            ),

        "fallback":
            llm_result.get(
                "fallback",
                False,
            ),

        "success":
            llm_result.get(
                "success",
                True,
            ),

        "answer":
            llm_result.get(
                "content",
                "",
            ),
    }


