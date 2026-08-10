from __future__ import annotations

import concurrent.futures
import time
import uuid
from dataclasses import (
    asdict,
    dataclass,
)
from typing import Any

from core.default_tools import (
    registry,
)

from core.tool_registry import (
    ToolRegistry,
    ToolSpec,
)


@dataclass
class ToolExecutionResult:

    execution_id: str

    tool_name: str

    success: bool

    status: str

    output: dict[str, Any] | None

    error: str | None

    duration_ms: float

    timed_out: bool

    blocked: bool

    validation_errors: list[str]

    def to_dict(self) -> dict:

        return asdict(
            self
        )


class ToolExecutor:

    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
    ):

        self.registry = (
            tool_registry
            if tool_registry is not None
            else registry
        )


    # ========================================================
    # BASIC SCHEMA VALIDATION
    # ========================================================

    def validate_arguments(
        self,
        spec: ToolSpec,
        arguments: dict[str, Any],
    ) -> list[str]:

        errors: list[str] = []

        schema = (
            spec.input_schema
            or {}
        )

        properties = (
            schema.get(
                "properties",
                {},
            )
            or {}
        )

        required = (
            schema.get(
                "required",
                [],
            )
            or []
        )


        # ----------------------------------------------------
        # REQUIRED
        # ----------------------------------------------------

        for field in required:

            if field not in arguments:

                errors.append(
                    f"Campo obrigatorio ausente: {field}"
                )


        # ----------------------------------------------------
        # TYPES
        # ----------------------------------------------------

        type_map = {
            "string":
                str,

            "integer":
                int,

            "number":
                (int, float),

            "boolean":
                bool,

            "object":
                dict,

            "array":
                list,
        }


        for name, value in arguments.items():

            rule = properties.get(
                name
            )

            if rule is None:

                errors.append(
                    f"Campo nao permitido: {name}"
                )

                continue


            expected_type = rule.get(
                "type"
            )


            if expected_type:

                python_type = (
                    type_map.get(
                        expected_type
                    )
                )

                if (
                    python_type is not None
                    and not isinstance(
                        value,
                        python_type,
                    )
                ):

                    errors.append(
                        (
                            f"Tipo invalido para {name}: "
                            f"esperado {expected_type}"
                        )
                    )

                    continue


            # ------------------------------------------------
            # NUMERIC BOUNDS
            # ------------------------------------------------

            if isinstance(
                value,
                (int, float),
            ):

                minimum = rule.get(
                    "minimum"
                )

                maximum = rule.get(
                    "maximum"
                )


                if (
                    minimum is not None
                    and value < minimum
                ):

                    errors.append(
                        (
                            f"{name} abaixo do minimo "
                            f"{minimum}"
                        )
                    )


                if (
                    maximum is not None
                    and value > maximum
                ):

                    errors.append(
                        (
                            f"{name} acima do maximo "
                            f"{maximum}"
                        )
                    )


        return errors


    # ========================================================
    # EXECUTION
    # ========================================================

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        allow_sensitive: bool = True,
        allow_network: bool = True,
        confirmed: bool = False,
    ) -> ToolExecutionResult:

        execution_id = str(
            uuid.uuid4()
        )

        start = time.perf_counter()

        arguments = (
            arguments
            if isinstance(
                arguments,
                dict,
            )
            else {}
        )


        # ----------------------------------------------------
        # TOOL EXISTS
        # ----------------------------------------------------

        spec = self.registry.get(
            tool_name
        )


        if spec is None:

            return ToolExecutionResult(
                execution_id=execution_id,

                tool_name=tool_name,

                success=False,

                status="not_found",

                output=None,

                error=(
                    f"Tool nao encontrada: {tool_name}"
                ),

                duration_ms=round(
                    (
                        time.perf_counter()
                        - start
                    ) * 1000,
                    3,
                ),

                timed_out=False,

                blocked=True,

                validation_errors=[],
            )


        # ----------------------------------------------------
        # ENABLED
        # ----------------------------------------------------

        if not spec.enabled:

            return ToolExecutionResult(
                execution_id=execution_id,

                tool_name=tool_name,

                success=False,

                status="disabled",

                output=None,

                error=(
                    f"Tool desabilitada: {tool_name}"
                ),

                duration_ms=round(
                    (
                        time.perf_counter()
                        - start
                    ) * 1000,
                    3,
                ),

                timed_out=False,

                blocked=True,

                validation_errors=[],
            )


        # ----------------------------------------------------
        # SENSITIVE POLICY
        # ----------------------------------------------------

        if (
            spec.sensitive
            and not allow_sensitive
        ):

            return ToolExecutionResult(
                execution_id=execution_id,

                tool_name=tool_name,

                success=False,

                status="sensitive_blocked",

                output=None,

                error=(
                    "Execucao de ferramenta sensivel "
                    "nao permitida."
                ),

                duration_ms=round(
                    (
                        time.perf_counter()
                        - start
                    ) * 1000,
                    3,
                ),

                timed_out=False,

                blocked=True,

                validation_errors=[],
            )


        # ----------------------------------------------------
        # NETWORK POLICY
        # ----------------------------------------------------

        if (
            spec.requires_network
            and not allow_network
        ):

            return ToolExecutionResult(
                execution_id=execution_id,

                tool_name=tool_name,

                success=False,

                status="network_blocked",

                output=None,

                error=(
                    "Ferramenta requer rede, "
                    "mas acesso a rede foi bloqueado."
                ),

                duration_ms=round(
                    (
                        time.perf_counter()
                        - start
                    ) * 1000,
                    3,
                ),

                timed_out=False,

                blocked=True,

                validation_errors=[],
            )


        # ----------------------------------------------------
        # CONFIRMATION POLICY
        # ----------------------------------------------------

        if (
            spec.requires_confirmation
            and not confirmed
        ):

            return ToolExecutionResult(
                execution_id=execution_id,

                tool_name=tool_name,

                success=False,

                status="confirmation_required",

                output=None,

                error=(
                    "Ferramenta requer confirmacao."
                ),

                duration_ms=round(
                    (
                        time.perf_counter()
                        - start
                    ) * 1000,
                    3,
                ),

                timed_out=False,

                blocked=True,

                validation_errors=[],
            )


        # ----------------------------------------------------
        # ARGUMENT VALIDATION
        # ----------------------------------------------------

        validation_errors = (
            self.validate_arguments(
                spec,
                arguments,
            )
        )


        if validation_errors:

            return ToolExecutionResult(
                execution_id=execution_id,

                tool_name=tool_name,

                success=False,

                status="validation_error",

                output=None,

                error=(
                    "Argumentos invalidos."
                ),

                duration_ms=round(
                    (
                        time.perf_counter()
                        - start
                    ) * 1000,
                    3,
                ),

                timed_out=False,

                blocked=True,

                validation_errors=
                    validation_errors,
            )


        # ----------------------------------------------------
        # HANDLER WITH TIMEOUT
        # ----------------------------------------------------

        pool = None

        try:

            pool = (
                concurrent.futures.ThreadPoolExecutor(
                    max_workers=1
                )
            )

            future = pool.submit(
                spec.handler,
                arguments,
            )

            try:

                output = future.result(
                    timeout=
                        spec.timeout_seconds
                )


            except concurrent.futures.TimeoutError:

                future.cancel()

                pool.shutdown(
                    wait=False,
                    cancel_futures=True,
                )

                pool = None

                return ToolExecutionResult(
                    execution_id=
                        execution_id,

                    tool_name=
                        tool_name,

                    success=False,

                    status="timeout",

                    output=None,

                    error=(
                        "Tool excedeu o timeout "
                        f"de {spec.timeout_seconds}s."
                    ),

                    duration_ms=round(
                        (
                            time.perf_counter()
                            - start
                        ) * 1000,
                        3,
                    ),

                    timed_out=True,

                    blocked=False,

                    validation_errors=[],
                )


        except Exception as exc:

            return ToolExecutionResult(
                execution_id=
                    execution_id,

                tool_name=
                    tool_name,

                success=False,

                status="executor_error",

                output=None,

                error=
                    str(exc),

                duration_ms=round(
                    (
                        time.perf_counter()
                        - start
                    ) * 1000,
                    3,
                ),

                timed_out=False,

                blocked=False,

                validation_errors=[],
            )

        finally:

            if pool is not None:

                pool.shutdown(
                    wait=True,
                    cancel_futures=False,
                )


        # ----------------------------------------------------
        # NORMALIZE HANDLER RESULT
        # ----------------------------------------------------

        if not isinstance(
            output,
            dict,
        ):

            output = {
                "success": True,
                "result":
                    output,
            }


        handler_success = bool(
            output.get(
                "success",
                True,
            )
        )


        status = (
            "success"
            if handler_success
            else "tool_error"
        )


        return ToolExecutionResult(
            execution_id=
                execution_id,

            tool_name=
                tool_name,

            success=
                handler_success,

            status=
                status,

            output=
                output,

            error=(
                None
                if handler_success
                else str(
                    output.get(
                        "error",
                        "Tool retornou erro.",
                    )
                )
            ),

            duration_ms=round(
                (
                    time.perf_counter()
                    - start
                ) * 1000,
                3,
            ),

            timed_out=False,

            blocked=False,

            validation_errors=[],
        )


executor = ToolExecutor()


def execute_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    **kwargs,
) -> dict:

    return executor.execute(
        tool_name=
            tool_name,

        arguments=
            arguments,

        **kwargs,
    ).to_dict()

