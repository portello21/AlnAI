from __future__ import annotations

from typing import Any

from core.sandbox import (
    run_code,
)

from core.tool_registry import (
    ToolSpec,
)


def python_sandbox_handler(
    arguments: dict[str, Any],
) -> dict[str, Any]:

    code = str(
        arguments.get(
            "code",
            "",
        )
    )

    if not code.strip():

        return {
            "success": False,
            "error":
                "Codigo vazio.",
        }


    try:

        result = run_code(
            code
        )

        return {
            "success": True,
            "output":
                result,
        }


    except Exception as exc:

        return {
            "success": False,
            "error":
                str(exc),
        }


PYTHON_SANDBOX_TOOL = ToolSpec(

    name="python_sandbox",

    description=(
        "Executa codigo Python "
        "no sandbox controlado do ROG AI."
    ),

    category="code",

    handler=python_sandbox_handler,

    input_schema={
        "type": "object",

        "properties": {

            "code": {
                "type": "string",
                "description":
                    "Codigo Python a executar.",
            },
        },

        "required": [
            "code",
        ],
    },

    timeout_seconds=15.0,

    enabled=True,

    sensitive=True,

    requires_network=False,

    requires_confirmation=False,
)
