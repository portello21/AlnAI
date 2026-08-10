from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)
from typing import Any, Callable


ToolHandler = Callable[
    [dict[str, Any]],
    dict[str, Any],
]


@dataclass(frozen=True)
class ToolSpec:

    name: str

    description: str

    category: str

    handler: ToolHandler

    input_schema: dict[str, Any]

    timeout_seconds: float = 30.0

    enabled: bool = True

    sensitive: bool = False

    requires_network: bool = False

    requires_confirmation: bool = False


    def public_dict(self) -> dict:

        data = asdict(
            self
        )

        data.pop(
            "handler",
            None,
        )

        return data


class ToolRegistry:

    def __init__(self):

        self._tools: dict[
            str,
            ToolSpec,
        ] = {}


    def register(
        self,
        spec: ToolSpec,
        overwrite: bool = False,
    ) -> None:

        name = (
            spec.name
            or ""
        ).strip()

        if not name:

            raise ValueError(
                "Tool name vazio."
            )

        if (
            name in self._tools
            and not overwrite
        ):

            raise ValueError(
                f"Tool ja registrada: {name}"
            )

        self._tools[
            name
        ] = spec


    def unregister(
        self,
        name: str,
    ) -> bool:

        return (
            self._tools.pop(
                name,
                None,
            )
            is not None
        )


    def get(
        self,
        name: str,
    ) -> ToolSpec | None:

        return self._tools.get(
            name
        )


    def require(
        self,
        name: str,
    ) -> ToolSpec:

        spec = self.get(
            name
        )

        if spec is None:

            raise KeyError(
                f"Tool nao encontrada: {name}"
            )

        return spec


    def exists(
        self,
        name: str,
    ) -> bool:

        return (
            name in self._tools
        )


    def list_tools(
        self,
        enabled_only: bool = False,
    ) -> list[ToolSpec]:

        tools = list(
            self._tools.values()
        )

        if enabled_only:

            tools = [
                tool
                for tool in tools
                if tool.enabled
            ]

        return sorted(
            tools,
            key=lambda item:
                item.name,
        )


    def public_tools(
        self,
        enabled_only: bool = True,
    ) -> list[dict]:

        return [
            tool.public_dict()
            for tool in self.list_tools(
                enabled_only=
                    enabled_only
            )
        ]


registry = ToolRegistry()


def register_tool(
    spec: ToolSpec,
    overwrite: bool = False,
) -> None:

    registry.register(
        spec,
        overwrite=overwrite,
    )


def get_tool(
    name: str,
) -> ToolSpec | None:

    return registry.get(
        name
    )


def list_tools(
    enabled_only: bool = True,
) -> list[ToolSpec]:

    return registry.list_tools(
        enabled_only=
            enabled_only
    )
