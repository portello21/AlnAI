from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)

from typing import Any

from core.execution_engine import (
    ExecutionContext,
    ExecutionEngine,
    ExecutionPolicy,
    ExecutionResult,
)

from core.planner import (
    ExecutionPlan,
    TaskPlanner,
)

from core.runtime_adapter import (
    AgentRuntimeAdapter,
)

from core.source_grounding import (
    SourceGroundingEngine,
    SourceReference,
)

from core.claim_grounding import (
    ClaimGroundingEngine,
    ClaimGroundingResult,
)

from core.task_analyzer import (
    TaskAnalysis,
    analyze_task,
)


@dataclass
class WorkflowResult:

    success: bool

    status: str

    query: str

    analysis: TaskAnalysis

    plan: ExecutionPlan

    execution: ExecutionResult

    final_answer: str

    final_step_id: int | None

    model: str | None

    provider: str | None

    selected_agent: str | None

    sources: tuple[
        SourceReference,
        ...
    ] = ()

    cited_source_ids: tuple[
        str,
        ...
    ] = ()

    invalid_citations: tuple[
        str,
        ...
    ] = ()

    grounded: bool = False

    claim_count: int = 0

    supported_claim_count: int = 0

    unsupported_claim_count: int = 0

    citation_coverage: float = 0.0

    grounding_score: float = 0.0

    claim_grounding: ClaimGroundingResult | None = None

    def to_dict(self) -> dict:

        return {
            "success":
                self.success,

            "status":
                self.status,

            "query":
                self.query,

            "analysis":
                self.analysis.to_dict(),

            "plan":
                self.plan.to_dict(),

            "execution":
                self.execution.to_dict(),

            "final_answer":
                self.final_answer,

            "final_step_id":
                self.final_step_id,

            "model":
                self.model,

            "provider":
                self.provider,

            "selected_agent":
                self.selected_agent,

            "sources": [
                source.to_dict()
                for source in self.sources
            ],

            "cited_source_ids":
                list(
                    self.cited_source_ids
                ),

            "invalid_citations":
                list(
                    self.invalid_citations
                ),

            "grounded":
                self.grounded,

            "claim_count":
                self.claim_count,

            "supported_claim_count":
                self.supported_claim_count,

            "unsupported_claim_count":
                self.unsupported_claim_count,

            "citation_coverage":
                self.citation_coverage,

            "grounding_score":
                self.grounding_score,

            "claim_grounding":
                (
                    self.claim_grounding.to_dict()
                    if self.claim_grounding
                    is not None
                    else None
                ),
        }


class WorkflowOrchestrator:

    def __init__(
        self,
        planner: TaskPlanner | None = None,
        execution_engine:
            ExecutionEngine | None = None,
        runtime_adapter:
            AgentRuntimeAdapter | None = None,
    ):

        self.planner = (
            planner
            or TaskPlanner()
        )

        self.runtime_adapter = (
            runtime_adapter
            or AgentRuntimeAdapter()
        )

        self.execution_engine = (
            execution_engine
            or ExecutionEngine(
                runtime_handler=
                    self.runtime_adapter.execute
            )
        )


    def _extract_final_output(
        self,
        execution: ExecutionResult,
    ) -> tuple[
        str,
        int | None,
        str | None,
        str | None,
        str | None,
    ]:

        preferred_actions = (
            "synthesize",
            "answer",
            "reason",
            "analyze_code",
        )


        candidates = [
            step
            for step in execution.steps
            if step.success
            and isinstance(
                step.output,
                dict,
            )
        ]


        for action in preferred_actions:

            for step in reversed(
                candidates
            ):

                if (
                    step.action
                    != action
                ):

                    continue


                answer = str(
                    step.output.get(
                        "answer",
                        "",
                    )
                    or ""
                ).strip()


                if not answer:

                    continue


                return (
                    answer,
                    step.step_id,
                    step.output.get(
                        "model"
                    ),
                    step.output.get(
                        "provider"
                    ),
                    step.output.get(
                        "selected_agent"
                    ),
                )


        return (
            "",
            None,
            None,
            None,
            None,
        )


    def run(
        self,
        query: str,
        history:
            list[dict[str, Any]] | None = None,
        profile: str | None = None,
        agent_id: str = "orchestrator",
        variables:
            dict[str, Any] | None = None,
        policy:
            ExecutionPolicy | None = None,
    ) -> WorkflowResult:

        query = str(
            query
            or ""
        ).strip()


        if not query:

            raise ValueError(
                "Workflow query vazia."
            )


        analysis = (
            analyze_task(
                query
            )
        )


        plan = (
            self.planner.create_plan(
                query=query,
                analysis=analysis,
            )
        )


        context = ExecutionContext(

            query=query,

            history=list(
                history
                or []
            ),

            profile=profile,

            agent_id=agent_id,

            variables=dict(
                variables
                or {}
            ),
        )


        execution = (
            self.execution_engine
            .execute(
                plan=plan,
                context=context,
                policy=(
                    policy
                    or ExecutionPolicy()
                ),
            )
        )


        (
            final_answer,
            final_step_id,
            model,
            provider,
            selected_agent,
        ) = self._extract_final_output(
            execution
        )


        success = bool(
            execution.success
            and final_answer
        )


        status = (
            "success"
            if success
            else execution.status
        )


        grounding = (
            SourceGroundingEngine()
            .validate(
                answer=final_answer,
                evidence_set=
                    execution
                    .context
                    .evidence_set,
            )
        )


        claim_grounding = None


        if grounding.sources:

            claim_grounding = (
                ClaimGroundingEngine()
                .analyze(
                    answer=final_answer,
                    sources=grounding.sources,
                    minimum_coverage=0.80,
                )
            )


        final_grounded = (
            grounding.grounded
        )


        if claim_grounding is not None:

            final_grounded = bool(
                grounding.grounded
                and claim_grounding.grounded
            )


        return WorkflowResult(

            success=success,

            status=status,

            query=query,

            analysis=analysis,

            plan=plan,

            execution=execution,

            final_answer=
                final_answer,

            final_step_id=
                final_step_id,

            model=model,

            provider=provider,

            selected_agent=
                selected_agent,

            sources=
                grounding.sources,

            cited_source_ids=
                grounding.cited_source_ids,

            invalid_citations=
                grounding.invalid_citations,

            grounded=
                final_grounded,

            claim_count=
                (
                    claim_grounding.claim_count
                    if claim_grounding
                    is not None
                    else 0
                ),

            supported_claim_count=
                (
                    claim_grounding
                    .validly_cited_claim_count
                    if claim_grounding
                    is not None
                    else 0
                ),

            unsupported_claim_count=
                (
                    claim_grounding
                    .unsupported_claim_count
                    if claim_grounding
                    is not None
                    else 0
                ),

            citation_coverage=
                (
                    claim_grounding
                    .valid_citation_coverage
                    if claim_grounding
                    is not None
                    else 0.0
                ),

            grounding_score=
                (
                    claim_grounding
                    .grounding_score
                    if claim_grounding
                    is not None
                    else 0.0
                ),

            claim_grounding=
                claim_grounding,
        )


workflow_orchestrator = (
    WorkflowOrchestrator()
)
