from core.tool_registry import (
    registry,
)

from tools.calculator import (
    CALCULATOR_TOOL,
)

from tools.python_sandbox import (
    PYTHON_SANDBOX_TOOL,
)

from tools.web_search import (
    WEB_SEARCH_TOOL,
)


def register_default_tools():

    defaults = [
        CALCULATOR_TOOL,
        PYTHON_SANDBOX_TOOL,
        WEB_SEARCH_TOOL,
    ]

    for tool in defaults:

        if not registry.exists(
            tool.name
        ):

            registry.register(
                tool
            )

    return registry


register_default_tools()
