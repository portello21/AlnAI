from __future__ import annotations

import json
from typing import Optional

from core.llm_router import chat_with_metadata


EXTRACTION_SYSTEM_PROMPT = """
Voce e um classificador de memoria de longo prazo.

Sua tarefa e decidir se a mensagem do usuario contem informacao
que vale a pena lembrar em conversas futuras.

NAO memorize:
- perguntas comuns
- pedidos temporarios
- conversa casual
- cumprimentos
- instrucoes de uma unica tarefa
- informacoes sem utilidade futura
- dados claramente momentaneos

MEMORIZE quando houver:
- preferencias duradouras
- metas
- rotina
- projetos importantes
- informacoes de trabalho
- fatos pessoais relevantes
- restricoes
- preferencias de comunicacao
- aprendizado em andamento
- informacoes financeiras estruturais
- configuracoes persistentes

Retorne SOMENTE JSON valido.

Formato para ignorar:

{
  "remember": false
}

Formato para memorizar:

{
  "remember": true,
  "memory_type": "fact|preference|goal|constraint|identity|routine|project|relationship|finance|work|learning|other",
  "content": "frase curta e autocontida",
  "importance": 0.0,
  "confidence": 0.0
}

Regras:
- importance entre 0 e 1
- confidence entre 0 e 1
- content deve fazer sentido isoladamente
- nao invente nada
- nao transforme pergunta em fato
"""


def _clean_json_text(value: str) -> str:
    value = (value or "").strip()

    if value.startswith("```"):
        lines = value.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        value = "\n".join(lines).strip()

    return value


def extract_memory_candidate(
    user_text: str,
    profile: Optional[str] = None,
) -> dict:

    user_text = (user_text or "").strip()

    if not user_text:
        return {
            "remember": False,
            "reason": "empty",
        }

    messages = [
        {
            "role": "system",
            "content": EXTRACTION_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": (
                f"Perfil: {profile or 'desconhecido'}\n\n"
                f"Mensagem:\n{user_text}"
            ),
        },
    ]

    result = chat_with_metadata(
        model="deepseek-chat",
        messages=messages,
        temperature=0,
        max_tokens=300,
    )

    if not result.get("success", False):
        return {
            "remember": False,
            "reason": "llm_failure",
            "provider": result.get("provider"),
        }

    raw = _clean_json_text(
        result.get("content", "")
    )

    try:
        data = json.loads(raw)
    except Exception:
        return {
            "remember": False,
            "reason": "invalid_json",
            "raw": raw[:500],
        }

    if not data.get("remember"):
        return {
            "remember": False,
            "reason": "not_worth_remembering",
        }

    memory_type = str(
        data.get("memory_type", "other")
    ).strip().lower()

    content = str(
        data.get("content", "")
    ).strip()

    if not content:
        return {
            "remember": False,
            "reason": "empty_content",
        }

    try:
        importance = float(
            data.get("importance", 0.5)
        )
    except Exception:
        importance = 0.5

    try:
        confidence = float(
            data.get("confidence", 0.8)
        )
    except Exception:
        confidence = 0.8

    importance = max(
        0.0,
        min(importance, 1.0)
    )

    confidence = max(
        0.0,
        min(confidence, 1.0)
    )

    return {
        "remember": True,
        "memory_type": memory_type,
        "content": content,
        "importance": importance,
        "confidence": confidence,
        "provider": result.get("provider"),
        "model": result.get("model"),
    }