from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.agent_runtime import (
    execute_agent,
)

from core.planner import (
    PlanStep,
)

from core.source_grounding import (
    SourceGroundingEngine,
)


@dataclass
class RuntimeStepResponse:

    success: bool

    output: dict[str, Any] | None

    error: str | None = None


class AgentRuntimeAdapter:

    source_grounding_engine = SourceGroundingEngine()


    """
    Adapter entre ExecutionEngine e agent_runtime.

    ExecutionEngine nao importa agent_runtime diretamente.
    Isso evita acoplamento forte e facilita testes.
    """

    ACTION_INSTRUCTIONS = {

        "answer": (
            "Responda diretamente a solicitacao "
            "do usuario usando o contexto disponivel."
        ),

        "reason": (
            "Analise o problema cuidadosamente, "
            "considere os resultados das etapas anteriores "
            "e produza raciocinio conclusivo para a resposta."
        ),

        "analyze_code": (
            "Analise tecnicamente o codigo ou problema "
            "descrito pelo usuario. Identifique erros, "
            "causas provaveis e melhorias."
        ),

        "synthesize": (
            "Produza a resposta final ao usuario. "
            "Sintetize os resultados das etapas anteriores, "
            "nao invente dados e preserve incertezas "
            "ou conflitos encontrados."
        ),
    }


    def _safe_json(
        self,
        value: Any,
        max_chars: int = 12000,
    ) -> str:

        try:

            text = json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

        except Exception:

            text = str(
                value
            )


        if len(text) > max_chars:

            text = (
                text[:max_chars]
                + "\n...[context truncated]"
            )


        return text


    def _build_extra_context(
        self,
        step: PlanStep,
        context: Any,
    ) -> str:

        sections = []


        instruction = (
            self.ACTION_INSTRUCTIONS
            .get(
                step.action,
                (
                    "Execute a etapa solicitada "
                    "com base no contexto."
                ),
            )
        )


        sections.append(
            "EXECUTION STEP:\n"
            f"- action: {step.action}\n"
            f"- purpose: {step.purpose}\n"
            f"- instruction: {instruction}"
        )


        dependencies = (
            context.dependency_outputs(
                step
            )
        )


        if dependencies:

            sections.append(
                "RESULTADOS DAS ETAPAS ANTERIORES:\n"
                + self._safe_json(
                    dependencies
                )
            )


        if (
            getattr(
                context,
                "evidence_set",
                None,
            )
            is not None
        ):

            sections.append(
                "EVIDENCIAS DISPONIVEIS:\n"
                + self._safe_json(
                    context
                    .evidence_set
                    .to_dict()
                )
            )


        if (
            getattr(
                context,
                "verification_result",
                None,
            )
            is not None
        ):

            sections.append(
                "RESULTADO DA VERIFICACAO:\n"
                + self._safe_json(
                    context
                    .verification_result
                    .to_dict()
                )
            )


        evidence_set = getattr(
            context,
            "evidence_set",
            None,
        )

        if (
            evidence_set is not None
            and step.action in {
                "synthesize",
                "answer",
                "reason",
            }
        ):
            source_catalog = (
                self.source_grounding_engine
                .source_catalog(evidence_set)
            )

            if source_catalog:
                sections.append(
                    "REGRAS DE SOURCE GROUNDING:\n"
                    "Use obrigatoriamente os IDs [S1], [S2], [S3] etc. "
                    "junto das afirmacoes factuais derivadas da pesquisa.\n"
                    "Nao invente IDs.\n"
                    "Nao substitua [S#] apenas por links Markdown.\n"
                    "Cada afirmacao importante deve citar a fonte correspondente.\n"
                    "Se uma afirmacao nao estiver sustentada, declare a incerteza."
                )
                sections.append(source_catalog)

        return "\n\n".join(
            sections
        )


    def execute(
        self,
        step: PlanStep,
        context: Any,
    ) -> RuntimeStepResponse:

        try:

            extra_context = (
                self._build_extra_context(
                    step=step,
                    context=context,
                )
            )


            result = execute_agent(

                agent_id=(
                    getattr(
                        context,
                        "agent_id",
                        None,
                    )
                    or "orchestrator"
                ),

                history=(
                    getattr(
                        context,
                        "history",
                        None,
                    )
                    or []
                ),

                user_query=(
                    context.query
                ),

                extra_context=
                    extra_context,

                profile=(
                    getattr(
                        context,
                        "profile",
                        None,
                    )
                ),
            )


            success = bool(
                result.get(
                    "success",
                    True,
                )
            )


            if not success:

                return RuntimeStepResponse(
                    success=False,
                    output=result,
                    error=(
                        result.get(
                            "error"
                        )
                        or "Agent Runtime retornou failure."
                    ),
                )


            return RuntimeStepResponse(
                success=True,

                output={
                    "action":
                        step.action,

                    "answer":
                        result.get(
                            "answer",
                            "",
                        ),

                    "requested_agent":
                        result.get(
                            "requested_agent"
                        ),

                    "selected_agent":
                        result.get(
                            "selected_agent"
                        ),

                    "agent_name":
                        result.get(
                            "agent_name"
                        ),

                    "requested_model":
                        result.get(
                            "requested_model"
                        ),

                    "model":
                        result.get(
                            "model"
                        ),

                    "provider":
                        result.get(
                            "provider"
                        ),

                    "fallback":
                        result.get(
                            "fallback",
                            False,
                        ),

                    "profile":
                        result.get(
                            "profile"
                        ),

                    "memory_count":
                        result.get(
                            "memory_count",
                            result.get(
                                "memory_context_count",
                                0,
                            ),
                        ),

                    "memory_ids":
                        result.get(
                            "memory_ids",
                            result.get(
                                "memory_context_ids",
                                [],
                            ),
                        ),
                },

                error=None,
            )


        except Exception as exc:

            return RuntimeStepResponse(
                success=False,
                output=None,
                error=str(
                    exc
                ),
            )


agent_runtime_adapter = (
    AgentRuntimeAdapter()
)
