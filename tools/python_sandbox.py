from __future__ import annotations

from typing import Any

from core.sandbox import run_code
from core.tool_registry import ToolRisk, ToolSpec


def python_sandbox_handler(arguments: dict[str, Any]) -> dict[str, Any]:
    code = str(arguments.get("code", ""))
    if not code.strip():
        return {"success": False, "error": "Codigo vazio."}
    try:
        return {"success": True, "output": run_code(code)}
    except Exception as exc:
        return {"success": False, "error": type(exc).__name__}


PYTHON_SANDBOX_TOOL = ToolSpec(
    name="python_sandbox",
    description=(
        "Execucao local de Python. Desabilitada por padrao porque execucao "
        "de codigo no mesmo processo do app nao e uma fronteira de seguranca."
    ),
    category="code",
    handler=python_sandbox_handler,
    input_schema={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Codigo Python a executar."},
        },
        "required": ["code"],
    },
    timeout_seconds=15.0,
    enabled=False,
    sensitive=True,
    requires_network=False,
    requires_confirmation=True,
    risk=ToolRisk.DANGEROUS,
)
