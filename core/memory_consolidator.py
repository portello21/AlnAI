from __future__ import annotations

import json
from typing import Optional

from core.llm_router import chat_with_metadata
from core.memory_engine import MemoryEngine
from core.memory_extractor import extract_memory_candidate


CONSOLIDATION_PROMPT = """
Voce e o consolidador de memoria de longo prazo do ROG AI.

Compare uma NOVA MEMORIA candidata com memorias existentes
do mesmo perfil.

Retorne SOMENTE JSON valido.

Acoes permitidas:

CREATE
- informacao realmente nova

SKIP
- duplicada
- reformulacao equivalente
- nao adiciona informacao util

UPDATE
- nova informacao substitui/corrige uma memoria existente
- mudou preferencia, meta, trabalho, carro, projeto, rotina etc.

Formato CREATE:

{
  "action": "CREATE"
}

Formato SKIP:

{
  "action": "SKIP",
  "reason": "duplicada"
}

Formato UPDATE:

{
  "action": "UPDATE",
  "target_id": "id da memoria antiga",
  "content": "nova memoria consolidada",
  "memory_type": "tipo",
  "importance": 0.0,
  "confidence": 0.0
}

Regras:
- nunca invente fatos
- UPDATE somente quando houver contradicao ou substituicao clara
- nao use UPDATE apenas porque duas memorias sao relacionadas
- se forem fatos diferentes, use CREATE
- se forem semanticamente equivalentes, use SKIP
"""


def _clean_json(value: str) -> str:
    value = (value or "").strip()

    if value.startswith("```"):
        lines = value.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        value = "\n".join(lines).strip()

    return value


class MemoryConsolidator:

    def __init__(
        self,
        engine: Optional[MemoryEngine] = None,
    ):
        self.engine = engine or MemoryEngine()


    def decide(
        self,
        profile: str,
        candidate: dict,
    ) -> dict:

        if not candidate.get("remember"):
            return {
                "action": "SKIP",
                "reason": "candidate_not_memory",
            }

        content = candidate.get(
            "content",
            ""
        ).strip()

        if not content:
            return {
                "action": "SKIP",
                "reason": "empty_candidate",
            }

        existing = self.engine.list_memories(
            profile=profile,
            active_only=True,
            limit=100,
        )

        if not existing:
            return {
                "action": "CREATE"
            }

        # Pre-filtra memórias potencialmente relacionadas.
        related = self.engine.search_memories(
            profile=profile,
            query=content,
            limit=10,
        )

        # search_memories atual e lexical.
        # Se nao encontrar nada, ainda enviamos algumas memorias
        # mais importantes para detectar contradicoes indiretas.
        if not related:
            related = existing[:10]

        existing_payload = []

        for memory in related:
            existing_payload.append({
                "id": memory.get("id"),
                "memory_type": memory.get("memory_type"),
                "content": memory.get("content"),
                "importance": memory.get("importance"),
                "confidence": memory.get("confidence"),
            })

        messages = [
            {
                "role": "system",
                "content": CONSOLIDATION_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    "NOVA MEMORIA:\n"
                    + json.dumps(
                        candidate,
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n\nMEMORIAS EXISTENTES:\n"
                    + json.dumps(
                        existing_payload,
                        ensure_ascii=False,
                        indent=2,
                    )
                ),
            },
        ]

        result = chat_with_metadata(
            model="deepseek-chat",
            messages=messages,
            temperature=0,
            max_tokens=400,
        )

        if not result.get("success", False):
            return {
                "action": "CREATE",
                "reason": "consolidator_llm_failure",
            }

        raw = _clean_json(
            result.get("content", "")
        )

        try:
            decision = json.loads(raw)
        except Exception:
            return {
                "action": "CREATE",
                "reason": "invalid_json_fallback",
            }

        action = str(
            decision.get("action", "CREATE")
        ).strip().upper()

        if action not in {
            "CREATE",
            "SKIP",
            "UPDATE",
        }:
            action = "CREATE"

        decision["action"] = action

        return decision


    def process_text(
        self,
        profile: str,
        user_text: str,
        source: str = "automatic",
    ) -> dict:

        candidate = extract_memory_candidate(
            user_text=user_text,
            profile=profile,
        )

        if not candidate.get("remember"):
            return {
                "success": True,
                "action": "SKIP",
                "candidate": candidate,
                "memory": None,
            }

        decision = self.decide(
            profile=profile,
            candidate=candidate,
        )

        action = decision.get("action")

        if action == "SKIP":
            return {
                "success": True,
                "action": "SKIP",
                "candidate": candidate,
                "decision": decision,
                "memory": None,
            }

        if action == "CREATE":

            record = self.engine.add_memory(
                profile=profile,
                content=candidate["content"],
                memory_type=candidate.get(
                    "memory_type",
                    "other",
                ),
                importance=candidate.get(
                    "importance",
                    0.5,
                ),
                confidence=candidate.get(
                    "confidence",
                    0.8,
                ),
                source=source,
                metadata={
                    "automatic": True,
                    "consolidation_action": "CREATE",
                },
            )

            return {
                "success": True,
                "action": "CREATE",
                "candidate": candidate,
                "decision": decision,
                "memory": record,
            }

        if action == "UPDATE":

            target_id = decision.get(
                "target_id"
            )

            if not target_id:
                return {
                    "success": False,
                    "action": "UPDATE",
                    "error": "missing_target_id",
                    "candidate": candidate,
                    "decision": decision,
                }

            existing = self.engine.list_memories(
                profile=profile,
                active_only=True,
                limit=500,
            )

            target = next(
                (
                    memory
                    for memory in existing
                    if memory.get("id") == target_id
                ),
                None,
            )

            if not target:
                # Fallback seguro: nao apaga nada.
                record = self.engine.add_memory(
                    profile=profile,
                    content=candidate["content"],
                    memory_type=candidate.get(
                        "memory_type",
                        "other",
                    ),
                    importance=candidate.get(
                        "importance",
                        0.5,
                    ),
                    confidence=candidate.get(
                        "confidence",
                        0.8,
                    ),
                    source=source,
                    metadata={
                        "automatic": True,
                        "consolidation_action":
                            "CREATE_AFTER_INVALID_UPDATE",
                    },
                )

                return {
                    "success": True,
                    "action": "CREATE",
                    "candidate": candidate,
                    "decision": decision,
                    "memory": record,
                }

            new_content = str(
                decision.get(
                    "content",
                    candidate["content"],
                )
            ).strip()

            new_type = str(
                decision.get(
                    "memory_type",
                    candidate.get(
                        "memory_type",
                        target.get(
                            "memory_type",
                            "other",
                        ),
                    ),
                )
            ).strip().lower()

            try:
                new_importance = float(
                    decision.get(
                        "importance",
                        candidate.get(
                            "importance",
                            target.get(
                                "importance",
                                0.5,
                            ),
                        ),
                    )
                )
            except Exception:
                new_importance = candidate.get(
                    "importance",
                    0.5,
                )

            try:
                new_confidence = float(
                    decision.get(
                        "confidence",
                        candidate.get(
                            "confidence",
                            target.get(
                                "confidence",
                                0.8,
                            ),
                        ),
                    )
                )
            except Exception:
                new_confidence = candidate.get(
                    "confidence",
                    0.8,
                )

            # Primeiro cria a nova versao.
            new_record = self.engine.add_memory(
                profile=profile,
                content=new_content,
                memory_type=new_type,
                importance=new_importance,
                confidence=new_confidence,
                source=source,
                metadata={
                    "automatic": True,
                    "consolidation_action": "UPDATE",
                    "replaces_memory_id": target_id,
                },
            )

            # Somente depois desativa a antiga.
            forgot = self.engine.forget_memory(
                target_id
            )

            return {
                "success": True,
                "action": "UPDATE",
                "candidate": candidate,
                "decision": decision,
                "memory": new_record,
                "replaced_memory_id": target_id,
                "old_memory_deactivated": forgot,
            }

        return {
            "success": False,
            "action": action,
            "error": "unexpected_action",
        }