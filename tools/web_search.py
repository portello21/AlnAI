from __future__ import annotations

from typing import Any

from core.research_engine import (
    research_engine,
)

from core.tool_registry import (
    ToolSpec,
)


def web_search_handler(
    arguments: dict[str, Any],
) -> dict[str, Any]:

    query = str(
        arguments.get(
            "query",
            "",
        )
    ).strip()


    max_results = arguments.get(
        "max_results",
        5,
    )


    region = str(
        arguments.get(
            "region",
            "wt-wt",
        )
    ).strip()


    timelimit = arguments.get(
        "timelimit"
    )


    response = (
        research_engine.search(
            query=query,

            max_results=
                max_results,

            region=
                region,

            timelimit=
                timelimit,
        )
    )


    return response.to_dict()


WEB_SEARCH_TOOL = ToolSpec(

    name="web_search",

    description=(
        "Pesquisa informacoes atuais "
        "na web e retorna resultados "
        "estruturados com titulo, URL, "
        "snippet e dominio."
    ),

    category="research",

    handler=
        web_search_handler,

    input_schema={
        "type": "object",

        "properties": {

            "query": {
                "type": "string",

                "description":
                    "Consulta de pesquisa.",
            },

            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
            },

            "region": {
                "type": "string",
            },

            "timelimit": {
                "type": "string",
            },
        },

        "required": [
            "query",
        ],
    },

    timeout_seconds=
        12.0,

    enabled=True,

    sensitive=False,

    requires_network=True,

    requires_confirmation=False,
)
