from __future__ import annotations

import ast
import operator
from typing import Any

from core.tool_registry import (
    ToolSpec,
)


_ALLOWED_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


_ALLOWED_UNARY = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _evaluate(
    node: ast.AST,
) -> float | int:

    if isinstance(
        node,
        ast.Expression,
    ):

        return _evaluate(
            node.body
        )


    if isinstance(
        node,
        ast.Constant,
    ):

        if isinstance(
            node.value,
            (int, float),
        ):

            return node.value

        raise ValueError(
            "Constante nao permitida."
        )


    if isinstance(
        node,
        ast.BinOp,
    ):

        operator_type = type(
            node.op
        )

        if operator_type not in _ALLOWED_BINARY:

            raise ValueError(
                "Operador nao permitido."
            )

        left = _evaluate(
            node.left
        )

        right = _evaluate(
            node.right
        )

        return _ALLOWED_BINARY[
            operator_type
        ](
            left,
            right,
        )


    if isinstance(
        node,
        ast.UnaryOp,
    ):

        operator_type = type(
            node.op
        )

        if operator_type not in _ALLOWED_UNARY:

            raise ValueError(
                "Operador unario nao permitido."
            )

        return _ALLOWED_UNARY[
            operator_type
        ](
            _evaluate(
                node.operand
            )
        )


    raise ValueError(
        "Expressao nao permitida."
    )


def calculator_handler(
    arguments: dict[str, Any],
) -> dict[str, Any]:

    expression = str(
        arguments.get(
            "expression",
            "",
        )
    ).strip()

    if not expression:

        return {
            "success": False,
            "error":
                "Expression vazia.",
        }


    try:

        tree = ast.parse(
            expression,
            mode="eval",
        )

        result = _evaluate(
            tree
        )

        return {
            "success": True,
            "expression":
                expression,
            "result":
                result,
        }


    except Exception as exc:

        return {
            "success": False,
            "expression":
                expression,
            "error":
                str(exc),
        }


CALCULATOR_TOOL = ToolSpec(

    name="calculator",

    description=(
        "Executa calculos aritmeticos "
        "deterministicos."
    ),

    category="calculation",

    handler=calculator_handler,

    input_schema={
        "type": "object",

        "properties": {

            "expression": {
                "type": "string",
                "description":
                    "Expressao aritmetica.",
            },
        },

        "required": [
            "expression",
        ],
    },

    timeout_seconds=5.0,

    enabled=True,

    sensitive=False,

    requires_network=False,

    requires_confirmation=False,
)
