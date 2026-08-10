from __future__ import annotations

import time
import uuid

from dataclasses import (
    asdict,
    dataclass,
    field,
)

from typing import (
    Any,
    Callable,
)

from core.evidence_engine import (
    EvidenceEngine,
    EvidenceSet,
)

from core.multi_research import (
    MultiResearchEngine,
)

from core.planner import (
    ExecutionPlan,
    PlanStep,
)

from core.tool_executor import (
    ToolExecutionResult,
    ToolExecutor,
)

from core.verification_engine import (
    VerificationEngine,
    VerificationResult,
)


# ============================================================
# STEP STATES
# ============================================================


STEP_PENDING = "pending"
STEP_RUNNING = "running"
STEP_SUCCESS = "success"
STEP_FAILED = "failed"
STEP_BLOCKED = "blocked"
STEP_SKIPPED = "skipped"


TERMINAL_STATES = {
    STEP_SUCCESS,
    STEP_FAILED,
    STEP_BLOCKED,
    STEP_SKIPPED,
}


# ============================================================
# EXECUTION POLICY
# ============================================================


@dataclass(frozen=True)
class ExecutionPolicy:

    allow_sensitive: bool = False

    allow_network: bool = True

    confirmed: bool = False

    fail_fast: bool = True


# ============================================================
# EXECUTION CONTEXT
# ============================================================


@dataclass
class ExecutionContext:

    query: str

    history: list[dict[str, Any]] = field(
        default_factory=list
    )

    profile: str | None = None

    agent_id: str = "orchestrator"

    variables: dict[str, Any] = field(
        default_factory=dict
    )

    step_outputs: dict[
        int,
        Any,
    ] = field(
        default_factory=dict
    )

    evidence_set: EvidenceSet | None = None

    verification_result: VerificationResult | None = None

    def set_output(
        self,
        step_id: int,
        output: Any,
    ) -> None:

        self.step_outputs[
            step_id
        ] = output

    def get_output(
        self,
        step_id: int,
        default: Any = None,
    ) -> Any:

        return self.step_outputs.get(
            step_id,
            default,
        )

    def dependency_outputs(
        self,
        step: PlanStep,
    ) -> dict[int, Any]:

        return {
            dependency:
                self.step_outputs.get(
                    dependency
                )
            for dependency
            in step.depends_on
        }


# ============================================================
# STEP RESULT
# ============================================================


@dataclass
class StepExecutionResult:

    step_id: int

    action: str

    status: str

    success: bool

    purpose: str

    tool_name: str | None

    output: Any

    error: str | None

    duration_ms: float

    depends_on: tuple[int, ...]

    blocked_by: tuple[int, ...] = ()

    tool_execution: ToolExecutionResult | None = None

    def to_dict(self) -> dict:

        data = asdict(
            self
        )

        data[
            "depends_on"
        ] = list(
            self.depends_on
        )

        data[
            "blocked_by"
        ] = list(
            self.blocked_by
        )

        if self.tool_execution is not None:

            data[
                "tool_execution"
            ] = (
                self.tool_execution.to_dict()
            )

        return data


# ============================================================
# EXECUTION RESULT
# ============================================================


@dataclass
class ExecutionResult:

    execution_id: str

    success: bool

    status: str

    query: str

    duration_ms: float

    steps: tuple[
        StepExecutionResult,
        ...
    ]

    context: ExecutionContext

    failed_step_ids: tuple[int, ...]

    blocked_step_ids: tuple[int, ...]

    skipped_step_ids: tuple[int, ...]

    def to_dict(self) -> dict:

        return {
            "execution_id":
                self.execution_id,

            "success":
                self.success,

            "status":
                self.status,

            "query":
                self.query,

            "duration_ms":
                self.duration_ms,

            "steps": [
                step.to_dict()
                for step in self.steps
            ],

            "failed_step_ids":
                list(
                    self.failed_step_ids
                ),

            "blocked_step_ids":
                list(
                    self.blocked_step_ids
                ),

            "skipped_step_ids":
                list(
                    self.skipped_step_ids
                ),

            "step_outputs":
                dict(
                    self.context.step_outputs
                ),

            "evidence_set": (
                self.context
                .evidence_set
                .to_dict()
                if self.context.evidence_set
                is not None
                else None
            ),

            "verification_result": (
                self.context
                .verification_result
                .to_dict()
                if self.context
                .verification_result
                is not None
                else None
            ),
        }


# ============================================================
# RUNTIME HANDLER
# ============================================================


RuntimeHandler = Callable[
    [PlanStep, ExecutionContext],
    Any,
]


# ============================================================
# EXECUTION ENGINE
# ============================================================


class ExecutionEngine:

    def __init__(
        self,
        tool_executor:
            ToolExecutor | None = None,
        evidence_engine:
            EvidenceEngine | None = None,
        verification_engine:
            VerificationEngine | None = None,

        multi_research_engine:
            MultiResearchEngine | None = None,

        runtime_handler:
            RuntimeHandler | None = None,
    ):

        self.runtime_handler = (
            runtime_handler
        )

        self.multi_research_engine = (
            multi_research_engine
            or MultiResearchEngine()
        )

        self.tool_executor = (
            tool_executor
            or ToolExecutor()
        )

        self.evidence_engine = (
            evidence_engine
            or EvidenceEngine()
        )

        self.verification_engine = (
            verification_engine
            or VerificationEngine()
        )


    # ========================================================
    # DEPENDENCY RESOLUTION
    # ========================================================


    def _dependency_failures(
        self,
        step: PlanStep,
        result_map: dict[
            int,
            StepExecutionResult,
        ],
    ) -> tuple[int, ...]:

        failed = []

        for dependency in step.depends_on:

            result = result_map.get(
                dependency
            )

            if result is None:

                failed.append(
                    dependency
                )

                continue

            if result.status != STEP_SUCCESS:

                failed.append(
                    dependency
                )

        return tuple(
            failed
        )


    # ========================================================
    # TOOL ARGUMENTS
    # ========================================================


    def _tool_arguments(
        self,
        step: PlanStep,
        context: ExecutionContext,
    ) -> dict[str, Any]:

        action = step.action

        if action == "research":

            return {
                "query":
                    context.query,
            }

        if action == "calculate":

            expression = (
                context.variables.get(
                    "expression"
                )
            )

            if expression is None:

                expression = (
                    context.query
                )

            return {
                "expression":
                    expression,
            }

        if action == "execute_code":

            code = (
                context.variables.get(
                    "code"
                )
            )

            if code is None:

                code = (
                    context.query
                )

            return {
                "code":
                    code,
            }

        return {}


    # ========================================================
    # RESEARCH EVIDENCE
    # ========================================================


    def _build_research_evidence(
        self,
        output: Any,
        context: ExecutionContext,
    ) -> None:

        if not isinstance(
            output,
            dict,
        ):

            return

        results = output.get(
            "results"
        )

        if not isinstance(
            results,
            list,
        ):

            return

        evidence_set = (
            self.evidence_engine.build(
                query=context.query,
                results=results,
            )
        )

        context.evidence_set = (
            evidence_set
        )


    # ========================================================
    # INTERNAL ACTIONS
    # ========================================================


    def _execute_internal_action(
        self,
        step: PlanStep,
        context: ExecutionContext,
    ) -> tuple[
        bool,
        Any,
        str | None,
    ]:

        dependencies = (
            context.dependency_outputs(
                step
            )
        )

        if step.action in {
            "answer",
            "analyze_code",
            "reason",
            "synthesize",
        }:

            # ================================================
            # RUNTIME REAL
            # ================================================

            if self.runtime_handler is not None:

                runtime_result = (
                    self.runtime_handler(
                        step,
                        context,
                    )
                )


                runtime_success = bool(
                    getattr(
                        runtime_result,
                        "success",
                        False,
                    )
                    if not isinstance(
                        runtime_result,
                        dict,
                    )
                    else runtime_result.get(
                        "success",
                        False,
                    )
                )


                runtime_output = (
                    getattr(
                        runtime_result,
                        "output",
                        None,
                    )
                    if not isinstance(
                        runtime_result,
                        dict,
                    )
                    else runtime_result.get(
                        "output"
                    )
                )


                runtime_error = (
                    getattr(
                        runtime_result,
                        "error",
                        None,
                    )
                    if not isinstance(
                        runtime_result,
                        dict,
                    )
                    else runtime_result.get(
                        "error"
                    )
                )


                return (
                    runtime_success,
                    runtime_output,
                    runtime_error,
                )


            # ================================================
            # COMPATIBILITY FALLBACK
            #
            # Preserva comportamento da 7.8B quando nenhum
            # runtime handler foi injetado.
            # ================================================

            output = {
                "action":
                    step.action,

                "query":
                    context.query,

                "dependency_outputs":
                    dependencies,

                "deferred_to_runtime":
                    True,
            }

            return (
                True,
                output,
                None,
            )

        if step.action == "verify":

            if (
                context.evidence_set
                is None
            ):

                output = {
                    "verified":
                        False,

                    "reason":
                        "no_evidence_set",
                }

                return (
                    False,
                    output,
                    (
                        "Nao existe EvidenceSet "
                        "para verificacao."
                    ),
                )

            verification = (
                self.verification_engine
                .verify(
                    context.evidence_set
                )
            )

            context.verification_result = (
                verification
            )

            return (
                True,
                verification.to_dict(),
                None,
            )

        return (
            False,
            None,
            (
                "Action nao suportada "
                f"pelo ExecutionEngine: "
                f"{step.action}"
            ),
        )


    # ========================================================
    # HIGH LEVEL RESEARCH V2
    # ========================================================


    def _research_options(
        self,
        context: ExecutionContext,
    ) -> dict[str, Any]:

        variables = (
            context.variables
            or {}
        )


        def int_option(
            name: str,
            default: int,
            minimum: int,
            maximum: int,
        ) -> int:

            value = variables.get(
                name,
                default,
            )


            try:

                value = int(
                    value
                )

            except (
                TypeError,
                ValueError,
            ):

                value = default


            return max(
                minimum,
                min(
                    value,
                    maximum,
                ),
            )


        return {
            "max_queries":
                int_option(
                    "research_max_queries",
                    3,
                    1,
                    5,
                ),

            "results_per_query":
                int_option(
                    "research_results_per_query",
                    5,
                    1,
                    10,
                ),

            "max_merged_results":
                int_option(
                    "research_max_merged_results",
                    10,
                    1,
                    20,
                ),

            "region":
                str(
                    variables.get(
                        "research_region",
                        "wt-wt",
                    )
                    or "wt-wt"
                ),

            "safesearch":
                str(
                    variables.get(
                        "research_safesearch",
                        "moderate",
                    )
                    or "moderate"
                ),

            "timelimit":
                variables.get(
                    "research_timelimit"
                ),
        }


    def _execute_research_v2(
        self,
        step: PlanStep,
        context: ExecutionContext,
        policy: ExecutionPolicy,
    ) -> StepExecutionResult:

        start = time.perf_counter()


        # ====================================================
        # NETWORK POLICY
        # ====================================================

        if not policy.allow_network:

            return StepExecutionResult(

                step_id=
                    step.step_id,

                action=
                    step.action,

                status=
                    STEP_BLOCKED,

                success=False,

                purpose=
                    step.purpose,

                tool_name=
                    "multi_research",

                output=None,

                error=(
                    "Pesquisa externa bloqueada "
                    "pela politica allow_network=False."
                ),

                duration_ms=
                    round(
                        (
                            time.perf_counter()
                            - start
                        ) * 1000,
                        3,
                    ),

                depends_on=
                    step.depends_on,
            )


        try:

            options = (
                self._research_options(
                    context
                )
            )


            response = (
                self.multi_research_engine
                .search(
                    query=
                        context.query,

                    **options,
                )
            )


            if hasattr(
                response,
                "to_dict",
            ):

                output = (
                    response.to_dict()
                )

            elif isinstance(
                response,
                dict,
            ):

                output = dict(
                    response
                )

            else:

                raise TypeError(
                    "MultiResearchEngine retornou "
                    "formato nao suportado."
                )


            research_success = bool(
                output.get(
                    "success",
                    False,
                )
            )


            results = output.get(
                "results",
                [],
            )


            if (
                not research_success
                or not isinstance(
                    results,
                    list,
                )
                or not results
            ):

                return StepExecutionResult(

                    step_id=
                        step.step_id,

                    action=
                        step.action,

                    status=
                        STEP_FAILED,

                    success=False,

                    purpose=
                        step.purpose,

                    tool_name=
                        "multi_research",

                    output=
                        output,

                    error=(
                        output.get(
                            "error"
                        )
                        or (
                            "MultiResearch nao "
                            "retornou resultados."
                        )
                    ),

                    duration_ms=
                        round(
                            (
                                time.perf_counter()
                                - start
                            ) * 1000,
                            3,
                        ),

                    depends_on=
                        step.depends_on,
                )


            # =================================================
            # EVIDENCE V2
            # =================================================

            self._build_research_evidence(
                output=output,
                context=context,
            )


            if (
                context.evidence_set
                is None
            ):

                return StepExecutionResult(

                    step_id=
                        step.step_id,

                    action=
                        step.action,

                    status=
                        STEP_FAILED,

                    success=False,

                    purpose=
                        step.purpose,

                    tool_name=
                        "multi_research",

                    output=
                        output,

                    error=(
                        "Nao foi possivel construir "
                        "EvidenceSet da pesquisa."
                    ),

                    duration_ms=
                        round(
                            (
                                time.perf_counter()
                                - start
                            ) * 1000,
                            3,
                        ),

                    depends_on=
                        step.depends_on,
                )


            # =================================================
            # AUTOMATIC VERIFICATION V2
            #
            # Toda pesquisa recebe uma verificacao inicial.
            #
            # Um step 'verify' explicito ainda pode existir
            # depois no plano e recomputar o resultado.
            # =================================================

            verification = (
                self.verification_engine
                .verify(
                    context.evidence_set
                )
            )


            context.verification_result = (
                verification
            )


            # =================================================
            # ENRICH OUTPUT
            # =================================================

            output[
                "research_mode"
            ] = "multi_research_v2"


            output[
                "evidence"
            ] = (
                context.evidence_set
                .to_dict()
            )


            output[
                "verification"
            ] = (
                verification.to_dict()
            )


            return StepExecutionResult(

                step_id=
                    step.step_id,

                action=
                    step.action,

                status=
                    STEP_SUCCESS,

                success=True,

                purpose=
                    step.purpose,

                tool_name=
                    "multi_research",

                output=
                    output,

                error=None,

                duration_ms=
                    round(
                        (
                            time.perf_counter()
                            - start
                        ) * 1000,
                        3,
                    ),

                depends_on=
                    step.depends_on,
            )


        except Exception as exc:

            return StepExecutionResult(

                step_id=
                    step.step_id,

                action=
                    step.action,

                status=
                    STEP_FAILED,

                success=False,

                purpose=
                    step.purpose,

                tool_name=
                    "multi_research",

                output=None,

                error=str(
                    exc
                ),

                duration_ms=
                    round(
                        (
                            time.perf_counter()
                            - start
                        ) * 1000,
                        3,
                    ),

                depends_on=
                    step.depends_on,
            )


    # ========================================================
    # SINGLE STEP
    # ========================================================


    def _execute_step(
        self,
        step: PlanStep,
        context: ExecutionContext,
        policy: ExecutionPolicy,
    ) -> StepExecutionResult:

        start = time.perf_counter()

        tool_name = (
            step.tool_hint
        )

        try:

            # ------------------------------------------------
            # HIGH LEVEL RESEARCH
            #
            # Research e uma operacao composta:
            # MultiResearch -> Evidence -> Verification.
            # ------------------------------------------------

            if step.action == "research":

                return (
                    self._execute_research_v2(
                        step=step,
                        context=context,
                        policy=policy,
                    )
                )


            # ------------------------------------------------
            # TOOL STEP
            # ------------------------------------------------

            if tool_name:

                # verifier e uma action interna.
                if (
                    step.action == "verify"
                    and tool_name == "verifier"
                ):

                    success, output, error = (
                        self._execute_internal_action(
                            step=step,
                            context=context,
                        )
                    )

                    status = (
                        STEP_SUCCESS
                        if success
                        else STEP_FAILED
                    )

                    return StepExecutionResult(
                        step_id=
                            step.step_id,

                        action=
                            step.action,

                        status=
                            status,

                        success=
                            success,

                        purpose=
                            step.purpose,

                        tool_name=
                            tool_name,

                        output=
                            output,

                        error=
                            error,

                        duration_ms=
                            round(
                                (
                                    time.perf_counter()
                                    - start
                                ) * 1000,
                                3,
                            ),

                        depends_on=
                            step.depends_on,
                    )

                arguments = (
                    self._tool_arguments(
                        step=step,
                        context=context,
                    )
                )

                tool_result = (
                    self.tool_executor.execute(
                        tool_name=
                            tool_name,

                        arguments=
                            arguments,

                        allow_sensitive=
                            policy.allow_sensitive,

                        allow_network=
                            policy.allow_network,

                        confirmed=
                            policy.confirmed,
                    )
                )

                if tool_result.success:

                    output = (
                        tool_result.output
                    )

                    if (
                        step.action
                        == "research"
                    ):

                        self._build_research_evidence(
                            output=output,
                            context=context,
                        )

                    return StepExecutionResult(
                        step_id=
                            step.step_id,

                        action=
                            step.action,

                        status=
                            STEP_SUCCESS,

                        success=True,

                        purpose=
                            step.purpose,

                        tool_name=
                            tool_name,

                        output=
                            output,

                        error=None,

                        duration_ms=
                            round(
                                (
                                    time.perf_counter()
                                    - start
                                ) * 1000,
                                3,
                            ),

                        depends_on=
                            step.depends_on,

                        tool_execution=
                            tool_result,
                    )

                status = (
                    STEP_BLOCKED
                    if tool_result.blocked
                    else STEP_FAILED
                )

                return StepExecutionResult(
                    step_id=
                        step.step_id,

                    action=
                        step.action,

                    status=
                        status,

                    success=False,

                    purpose=
                        step.purpose,

                    tool_name=
                        tool_name,

                    output=
                        tool_result.output,

                    error=
                        tool_result.error,

                    duration_ms=
                        round(
                            (
                                time.perf_counter()
                                - start
                            ) * 1000,
                            3,
                        ),

                    depends_on=
                        step.depends_on,

                    tool_execution=
                        tool_result,
                )

            # ------------------------------------------------
            # INTERNAL STEP
            # ------------------------------------------------

            success, output, error = (
                self._execute_internal_action(
                    step=step,
                    context=context,
                )
            )

            return StepExecutionResult(
                step_id=
                    step.step_id,

                action=
                    step.action,

                status=(
                    STEP_SUCCESS
                    if success
                    else STEP_FAILED
                ),

                success=
                    success,

                purpose=
                    step.purpose,

                tool_name=None,

                output=
                    output,

                error=
                    error,

                duration_ms=
                    round(
                        (
                            time.perf_counter()
                            - start
                        ) * 1000,
                        3,
                    ),

                depends_on=
                    step.depends_on,
            )

        except Exception as exc:

            return StepExecutionResult(
                step_id=
                    step.step_id,

                action=
                    step.action,

                status=
                    STEP_FAILED,

                success=False,

                purpose=
                    step.purpose,

                tool_name=
                    tool_name,

                output=None,

                error=str(
                    exc
                ),

                duration_ms=
                    round(
                        (
                            time.perf_counter()
                            - start
                        ) * 1000,
                        3,
                    ),

                depends_on=
                    step.depends_on,
            )


    # ========================================================
    # PLAN EXECUTION
    # ========================================================


    def execute(
        self,
        plan: ExecutionPlan,
        context:
            ExecutionContext | None = None,
        policy:
            ExecutionPolicy | None = None,
    ) -> ExecutionResult:

        execution_id = str(
            uuid.uuid4()
        )

        start = time.perf_counter()

        if context is None:

            context = ExecutionContext(
                query=plan.query
            )

        if policy is None:

            policy = ExecutionPolicy()

        results: list[
            StepExecutionResult
        ] = []

        result_map: dict[
            int,
            StepExecutionResult
        ] = {}


        # ====================================================
        # EXECUTE STEPS
        # ====================================================


        for step in plan.steps:

            dependency_failures = (
                self._dependency_failures(
                    step=step,
                    result_map=result_map,
                )
            )

            if dependency_failures:

                skipped = (
                    StepExecutionResult(
                        step_id=
                            step.step_id,

                        action=
                            step.action,

                        status=
                            STEP_SKIPPED,

                        success=False,

                        purpose=
                            step.purpose,

                        tool_name=
                            step.tool_hint,

                        output=None,

                        error=(
                            "Dependencia nao concluida "
                            "com sucesso."
                        ),

                        duration_ms=0.0,

                        depends_on=
                            step.depends_on,

                        blocked_by=
                            dependency_failures,
                    )
                )

                results.append(
                    skipped
                )

                result_map[
                    step.step_id
                ] = skipped

                continue


            # ------------------------------------------------
            # FAIL FAST
            # ------------------------------------------------

            if (
                policy.fail_fast
                and any(
                    item.status
                    in {
                        STEP_FAILED,
                        STEP_BLOCKED,
                    }
                    for item in results
                )
            ):

                skipped = (
                    StepExecutionResult(
                        step_id=
                            step.step_id,

                        action=
                            step.action,

                        status=
                            STEP_SKIPPED,

                        success=False,

                        purpose=
                            step.purpose,

                        tool_name=
                            step.tool_hint,

                        output=None,

                        error=
                            "Execucao interrompida por fail_fast.",

                        duration_ms=0.0,

                        depends_on=
                            step.depends_on,
                    )
                )

                results.append(
                    skipped
                )

                result_map[
                    step.step_id
                ] = skipped

                continue


            result = (
                self._execute_step(
                    step=step,
                    context=context,
                    policy=policy,
                )
            )

            results.append(
                result
            )

            result_map[
                step.step_id
            ] = result

            if result.success:

                context.set_output(
                    step.step_id,
                    result.output,
                )


        # ====================================================
        # FINAL STATUS
        # ====================================================


        failed_ids = tuple(
            item.step_id
            for item in results
            if item.status
            == STEP_FAILED
        )

        blocked_ids = tuple(
            item.step_id
            for item in results
            if item.status
            == STEP_BLOCKED
        )

        skipped_ids = tuple(
            item.step_id
            for item in results
            if item.status
            == STEP_SKIPPED
        )

        success = (
            not failed_ids
            and not blocked_ids
            and not skipped_ids
            and all(
                item.status
                == STEP_SUCCESS
                for item in results
            )
        )

        if success:

            status = "success"

        elif blocked_ids:

            status = "blocked"

        elif failed_ids:

            status = "failed"

        else:

            status = "partial"


        return ExecutionResult(
            execution_id=
                execution_id,

            success=
                success,

            status=
                status,

            query=
                plan.query,

            duration_ms=
                round(
                    (
                        time.perf_counter()
                        - start
                    ) * 1000,
                    3,
                ),

            steps=
                tuple(
                    results
                ),

            context=
                context,

            failed_step_ids=
                failed_ids,

            blocked_step_ids=
                blocked_ids,

            skipped_step_ids=
                skipped_ids,
        )


execution_engine = (
    ExecutionEngine()
)
