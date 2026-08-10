from core.config import Config
from providers.deepseek import chat_deepseek
from providers.docker_model import chat_dmr, healthcheck_dmr


LOCAL_MODEL = "docker.io/ai/qwen3:latest"

LOCAL_MODELS = {
    "qwen3",
    LOCAL_MODEL,
}


def is_local_model(model: str) -> bool:
    normalized = (model or "").strip().lower()

    if normalized in LOCAL_MODELS:
        return True

    return "qwen3" in normalized


def is_error_response(value: str) -> bool:
    if not isinstance(value, str):
        return True

    normalized = value.strip().lower()

    if not normalized:
        return True

    error_prefixes = (
        "erro:",
        "erro ",
        "erro http",
        "error:",
        "error ",
    )

    return normalized.startswith(error_prefixes)


def chat_local(
    messages: list,
    temperature: float = 0.2,
    max_tokens=None,
) -> str:

    return chat_dmr(
        messages=messages,
        model=LOCAL_MODEL,
        temperature=temperature,
        max_tokens=max_tokens or 2048,
    )


def chat_with_metadata(
    model: str,
    messages: list,
    temperature: float = 0.2,
    max_tokens=None,
) -> dict:

    requested_model = model

    # ---------------------------------------------------------
    # Qwen solicitado diretamente
    # ---------------------------------------------------------
    if is_local_model(model):

        response = chat_local(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return {
            "content": response,
            "provider": "docker-model-runner",
            "requested_model": requested_model,
            "model": "qwen3",
            "fallback": False,
            "success": not is_error_response(response),
        }

    # ---------------------------------------------------------
    # DeepSeek principal
    # ---------------------------------------------------------
    primary_response = chat_deepseek(
        api_key=Config.DEEPSEEK_API,
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens or 4096,
    )

    if not is_error_response(primary_response):

        return {
            "content": primary_response,
            "provider": "deepseek",
            "requested_model": requested_model,
            "model": model,
            "fallback": False,
            "success": True,
        }

    # ---------------------------------------------------------
    # DeepSeek falhou -> Qwen local
    # ---------------------------------------------------------
    if healthcheck_dmr():

        fallback_response = chat_local(
            messages=messages,
            temperature=temperature,
            max_tokens=min(max_tokens or 2048, 2048),
        )

        if not is_error_response(fallback_response):

            return {
                "content": fallback_response,
                "provider": "docker-model-runner",
                "requested_model": requested_model,
                "model": "qwen3",
                "fallback": True,
                "success": True,
                "primary_error": primary_response,
            }

        return {
            "content": (
                "Erro: provider principal e fallback local falharam. "
                f"DeepSeek: {primary_response} | "
                f"Qwen3: {fallback_response}"
            ),
            "provider": "none",
            "requested_model": requested_model,
            "model": None,
            "fallback": True,
            "success": False,
            "primary_error": primary_response,
            "fallback_error": fallback_response,
        }

    return {
        "content": (
            "Erro: DeepSeek falhou e Qwen3 local nao esta disponivel. "
            f"Detalhe DeepSeek: {primary_response}"
        ),
        "provider": "none",
        "requested_model": requested_model,
        "model": None,
        "fallback": False,
        "success": False,
        "primary_error": primary_response,
    }


def chat(
    model: str,
    messages: list,
    temperature: float = 0.2,
    max_tokens=None,
) -> str:

    result = chat_with_metadata(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return result["content"]


def local_available() -> bool:
    return healthcheck_dmr()