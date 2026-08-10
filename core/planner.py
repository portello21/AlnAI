from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)

from core.task_analyzer import (
    TaskAnalysis,
    analyze_task,
)


# ============================================================
# PLAN DATA STRUCTURES
# ============================================================


@dataclass(frozen=True)
class PlanStep:

    step_id: int

    action: str

    purpose: str

    tool_hint: str | None = None

    requires_verification: bool = False

    depends_on: tuple[int, ...] = ()

    def to_dict(self) -> dict:

        data = asdict(self)

        data["depends_on"] = list(
            self.depends_on
        )

        return data


@dataclass(frozen=True)
class ExecutionPlan:

    query: str

    complexity: str

    direct_answer: bool

    requires_execution: bool

    steps: tuple[PlanStep, ...]

    analysis: TaskAnalysis

    def to_dict(self) -> dict:

        return {
            "query":
                self.query,

            "complexity":
                self.complexity,

            "direct_answer":
                self.direct_answer,

            "requires_execution":
                self.requires_execution,

            "steps": [
                step.to_dict()
                for step in self.steps
            ],

            "analysis":
                self.analysis.to_dict(),
        }


# ============================================================
# PLANNER
# ============================================================


class TaskPlanner:

    """
    Planner deterministico V1.

    Responsabilidade:

    TaskAnalysis
        ->
    ExecutionPlan

    Ele NAO executa ferramentas.
    Ele apenas descreve a sequencia de trabalho.
    """


    def create_plan(
        self,
        query: str,
        analysis: TaskAnalysis | None = None,
    ) -> ExecutionPlan:

        if analysis is None:

            analysis = analyze_task(
                query
            )


        # ====================================================
        # DIRECT ANSWER
        #
        # Nao existe necessidade objetiva de executar
        # ferramenta nem decompor a tarefa.
        # ====================================================

        direct_answer = (
            not analysis.needs_tools
            and not analysis.needs_planning
            and not analysis.needs_verification
        )


        if direct_answer:

            step = PlanStep(
                step_id=1,

                action="answer",

                purpose=(
                    "Responder diretamente a solicitacao "
                    "do usuario usando o contexto disponivel."
                ),

                tool_hint=None,

                requires_verification=False,

                depends_on=(),
            )

            return ExecutionPlan(
                query=query,

                complexity=
                    analysis.complexity,

                direct_answer=True,

                requires_execution=False,

                steps=(step,),

                analysis=analysis,
            )


        # ====================================================
        # EXECUTION PLAN
        # ====================================================

        steps: list[PlanStep] = []

        previous_step: int | None = None


        def add_step(
            action: str,
            purpose: str,
            tool_hint: str | None = None,
            requires_verification: bool = False,
        ) -> int:

            nonlocal previous_step

            step_id = (
                len(steps) + 1
            )

            dependencies = (
                (previous_step,)
                if previous_step is not None
                else ()
            )

            step = PlanStep(
                step_id=step_id,

                action=action,

                purpose=purpose,

                tool_hint=tool_hint,

                requires_verification=
                    requires_verification,

                depends_on=dependencies,
            )

            steps.append(
                step
            )

            previous_step = step_id

            return step_id


        # ====================================================
        # RESEARCH
        # ====================================================

        if analysis.needs_research:

            add_step(
                action="research",

                purpose=(
                    "Buscar informacoes externas relevantes "
                    "e reunir evidencia para responder "
                    "a solicitacao."
                ),

                tool_hint="web_search",

                requires_verification=True,
            )


        # ====================================================
        # CODE
        # ====================================================

        if analysis.needs_code:

            add_step(
                action="analyze_code",

                purpose=(
                    "Analisar o problema tecnico, codigo "
                    "ou comportamento do sistema."
                ),

                tool_hint=None,

                requires_verification=False,
            )

            add_step(
                action="execute_code",

                purpose=(
                    "Executar ou testar codigo quando isso "
                    "for necessario para validar a solucao."
                ),

                tool_hint="python_sandbox",

                requires_verification=True,
            )


        # ====================================================
        # CALCULATION
        # ====================================================

        if analysis.needs_calculation:

            add_step(
                action="calculate",

                purpose=(
                    "Executar os calculos necessarios "
                    "com precisao deterministica."
                ),

                tool_hint="calculator",

                requires_verification=True,
            )


        # ====================================================
        # GENERIC PLANNING
        # ====================================================

        if (
            analysis.needs_planning
            and not analysis.needs_code
        ):

            add_step(
                action="reason",

                purpose=(
                    "Decompor o problema e avaliar "
                    "as alternativas relevantes."
                ),

                tool_hint=None,

                requires_verification=False,
            )


        # ====================================================
        # VERIFICATION
        # ====================================================

        if analysis.needs_verification:

            add_step(
                action="verify",

                purpose=(
                    "Revisar resultados e verificar "
                    "consistencia, contradicoes e erros."
                ),

                tool_hint="verifier",

                requires_verification=False,
            )


        # ====================================================
        # FINAL SYNTHESIS
        # ====================================================

        add_step(
            action="synthesize",

            purpose=(
                "Combinar os resultados das etapas anteriores "
                "em uma resposta final clara e util."
            ),

            tool_hint=None,

            requires_verification=False,
        )


        return ExecutionPlan(
            query=query,

            complexity=
                analysis.complexity,

            direct_answer=False,

            requires_execution=True,

            steps=tuple(
                steps
            ),

            analysis=analysis,
        )


def create_plan(
    query: str,
    analysis: TaskAnalysis | None = None,
) -> ExecutionPlan:

    planner = TaskPlanner()

    return planner.create_plan(
        query=query,
        analysis=analysis,
    )
