from __future__ import annotations

from core.config import Config
from core.provider_policy import ProviderHealthRegistry, provider_allowed
from providers.deepseek import chat_deepseek
from providers.docker_model import chat_dmr, healthcheck_dmr
from providers.nvidia import chat_nvidia

LOCAL_MODEL = "docker.io/ai/qwen3:latest"
LOCAL_MODELS = {"qwen3", LOCAL_MODEL}
HEALTH = ProviderHealthRegistry()


def is_local_model(model: str) -> bool:
    normalized = (model or "").strip().lower()
    return normalized in LOCAL_MODELS or "qwen3" in normalized


def is_error_response(value: str) -> bool:
    if not isinstance(value, str) or not value.strip():
        return True
    normalized = value.strip().lower()
    return normalized.startswith(("erro:", "erro ", "erro http", "error:", "error "))


def _result(content: str, provider: str, requested_model: str, model: str | None, *, fallback: bool) -> dict:
    success = not is_error_response(content)
    if success:
        HEALTH.success(provider)
    elif provider != "none":
        HEALTH.failure(provider, "provider_error", rate_limited="429" in str(content))
    return {
        "content": content,
        "provider": provider,
        "requested_model": requested_model,
        "model": model,
        "fallback": fallback,
        "success": success,
    }


def chat_local(messages: list, temperature: float = 0.2, max_tokens=None) -> str:
    return chat_dmr(
        messages=messages,
        model=LOCAL_MODEL,
        temperature=temperature,
        max_tokens=max_tokens or 2048,
    )


def _try_local(requested_model: str, messages: list, temperature: float, max_tokens, *, fallback: bool) -> dict | None:
    provider = "docker-model-runner"
    if not provider_allowed(provider, allow_paid=Config.ALLOW_PAID_PROVIDERS) or not HEALTH.can_attempt(provider):
        return None
    if fallback and not healthcheck_dmr():
        HEALTH.failure(provider, "healthcheck")
        return None
    response = chat_local(messages, temperature, max_tokens)
    return _result(response, provider, requested_model, "qwen3", fallback=fallback)


def _try_nvidia(requested_model: str, messages: list, temperature: float, max_tokens, *, fallback: bool) -> dict | None:
    provider = "nvidia"
    if not Config.status().get("nvidia") or not provider_allowed(provider, allow_paid=Config.ALLOW_PAID_PROVIDERS):
        return None
    if not HEALTH.can_attempt(provider):
        return None
    response = chat_nvidia(
        Config.NVIDIA_API,
        Config.NVIDIA_BASE_URL,
        Config.NVIDIA_MODEL,
        messages,
        temperature,
        max_tokens or 4096,
    )
    return _result(response, provider, requested_model, Config.NVIDIA_MODEL, fallback=fallback)


def _try_deepseek(requested_model: str, messages: list, temperature: float, max_tokens, *, fallback: bool) -> dict | None:
    provider = "deepseek"
    if not Config.DEEPSEEK_API or not HEALTH.can_attempt(provider):
        return None
    # Backward compatibility: an explicitly requested DeepSeek model is allowed
    # because existing deployments already opted into it by configuring its key.
    explicitly_requested = str(requested_model or "").startswith("deepseek-")
    if not explicitly_requested and not provider_allowed(provider, allow_paid=Config.ALLOW_PAID_PROVIDERS):
        return None
    response = chat_deepseek(
        api_key=Config.DEEPSEEK_API,
        messages=messages,
        model=requested_model if explicitly_requested else "deepseek-chat",
        temperature=temperature,
        max_tokens=max_tokens or 4096,
    )
    return _result(response, provider, requested_model, requested_model, fallback=fallback)


def chat_with_metadata(model: str, messages: list, temperature: float = 0.2, max_tokens=None) -> dict:
    requested_model = model or "auto"

    if is_local_model(requested_model):
        local = _try_local(requested_model, messages, temperature, max_tokens, fallback=False)
        if local is not None:
            return local

    mode = Config.PROVIDER_MODE
    attempts = []
    if mode in {"local", "qwen"}:
        attempts = ["local"]
    elif mode == "nvidia":
        attempts = ["nvidia", "local"]
    elif mode == "deepseek":
        attempts = ["deepseek", "local"]
    else:
        # Free/local first. DeepSeek remains available for explicit legacy model
        # requests, but a new deployment does not silently enable paid APIs.
        attempts = ["local", "nvidia", "deepseek"] if not str(requested_model).startswith("deepseek-") else ["deepseek", "local", "nvidia"]

    errors: list[str] = []
    for index, candidate in enumerate(attempts):
        if candidate == "local":
            result = _try_local(requested_model, messages, temperature, max_tokens, fallback=index > 0)
        elif candidate == "nvidia":
            result = _try_nvidia(requested_model, messages, temperature, max_tokens, fallback=index > 0)
        else:
            result = _try_deepseek(requested_model, messages, temperature, max_tokens, fallback=index > 0)
        if result is None:
            continue
        if result["success"]:
            return result
        errors.append(f"{candidate}:{result['content'][:120]}")

    return {
        "content": "Nenhum provider de IA permitido e disponível respondeu. Verifique o modelo local ou as integrações configuradas.",
        "provider": "none",
        "requested_model": requested_model,
        "model": None,
        "fallback": bool(errors),
        "success": False,
        "errors": errors,
    }


def chat(model: str, messages: list, temperature: float = 0.2, max_tokens=None) -> str:
    return chat_with_metadata(model, messages, temperature, max_tokens)["content"]


def local_available() -> bool:
    return healthcheck_dmr()
