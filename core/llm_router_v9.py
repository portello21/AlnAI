from __future__ import annotations

import time

from core.config import Config
from core.provider_policy import ProviderHealthRegistry, provider_allowed
from core.telemetry import record_runtime_event
from providers.deepseek import chat_deepseek
from providers.docker_model import chat_dmr, healthcheck_dmr
from providers.nvidia import chat_nvidia

LOCAL_MODEL = "docker.io/ai/qwen3:latest"
HEALTH = ProviderHealthRegistry()


def is_local_model(model: str) -> bool:
    value = str(model or "").strip().lower()
    return value in {"qwen3", LOCAL_MODEL} or "qwen3" in value


def is_error_response(value: str) -> bool:
    if not isinstance(value, str) or not value.strip():
        return True
    value = value.strip().lower()
    return value.startswith(("erro:", "erro ", "erro http", "error:", "error "))


def _error_type(content: str) -> tuple[str, bool]:
    value = str(content or "").lower()
    if "429" in value or "rate limit" in value or "rate_limit" in value:
        return "rate_limit", True
    if "timeout" in value:
        return "timeout", False
    if "401" in value or "403" in value:
        return "authentication", False
    return "provider_error", False


def _finish(content: str, provider: str, requested_model: str, model: str | None, fallback: bool) -> dict:
    success = not is_error_response(content)
    error_type = ""
    if success:
        HEALTH.success(provider)
    elif provider != "none":
        error_type, limited = _error_type(content)
        HEALTH.failure(provider, error_type, rate_limited=limited)
    return {
        "content": content,
        "provider": provider,
        "requested_model": requested_model,
        "model": model,
        "fallback": fallback,
        "success": success,
        "error_type": error_type,
    }


def chat_local(messages: list, temperature: float = 0.2, max_tokens=None) -> str:
    return chat_dmr(messages=messages, model=LOCAL_MODEL, temperature=temperature, max_tokens=max_tokens or 2048)


def _local(requested_model: str, messages: list, temperature: float, max_tokens, fallback: bool) -> dict | None:
    provider = "docker-model-runner"
    if not HEALTH.can_attempt(provider):
        return None
    if fallback and not healthcheck_dmr():
        HEALTH.failure(provider, "healthcheck")
        return None
    return _finish(chat_local(messages, temperature, max_tokens), provider, requested_model, "qwen3", fallback)


def _nvidia(requested_model: str, messages: list, temperature: float, max_tokens, fallback: bool) -> dict | None:
    provider = "nvidia"
    if not Config.status().get("nvidia") or not HEALTH.can_attempt(provider):
        return None
    if not provider_allowed(provider, allow_paid=Config.ALLOW_PAID_PROVIDERS):
        return None
    value = chat_nvidia(
        Config.NVIDIA_API,
        Config.NVIDIA_BASE_URL,
        Config.NVIDIA_MODEL,
        messages,
        temperature,
        max_tokens or 4096,
        timeout=Config.NVIDIA_TIMEOUT_SECONDS,
    )
    return _finish(value, provider, requested_model, Config.NVIDIA_MODEL, fallback)


def _deepseek(requested_model: str, messages: list, temperature: float, max_tokens, fallback: bool) -> dict | None:
    provider = "deepseek"
    if not Config.DEEPSEEK_API or not HEALTH.can_attempt(provider):
        return None
    if not provider_allowed(provider, allow_paid=Config.ALLOW_PAID_PROVIDERS):
        return None
    model = requested_model if str(requested_model).startswith("deepseek-") else "deepseek-chat"
    value = chat_deepseek(api_key=Config.DEEPSEEK_API, messages=messages, model=model, temperature=temperature, max_tokens=max_tokens or 4096)
    return _finish(value, provider, requested_model, model, fallback)


def attempt_order(requested_model: str) -> tuple[str, ...]:
    """Return provider order without making the hosted family app depend on a PC.

    Auto mode prefers NVIDIA NIM when configured, then the local Qwen fallback,
    and only then paid DeepSeek when the explicit cost guard permits it.
    """
    mode = Config.PROVIDER_MODE
    if Config.IS_CLOUD:
        # A hosted Streamlit process has no Docker Model Runner. Once NVIDIA
        # fails, return promptly instead of probing localhost and compounding
        # the user-visible timeout. Paid providers still require explicit opt-in.
        return ("nvidia", "deepseek") if Config.ALLOW_PAID_PROVIDERS else ("nvidia",)
    if mode in {"local", "qwen"}:
        return ("local",)
    if mode == "nvidia":
        return ("nvidia", "local", "deepseek")
    if mode == "deepseek":
        return ("deepseek", "nvidia", "local")
    return ("nvidia", "local", "deepseek")


def chat_with_metadata(model: str, messages: list, temperature: float = 0.2, max_tokens=None) -> dict:
    requested_model = str(model or "auto")
    attempted: list[str] = []
    failures: list[dict[str, str]] = []
    for index, candidate in enumerate(attempt_order(requested_model)):
        fallback = index > 0
        started = time.monotonic()
        if candidate == "local":
            result = _local(requested_model, messages, temperature, max_tokens, fallback)
        elif candidate == "nvidia":
            result = _nvidia(requested_model, messages, temperature, max_tokens, fallback)
        else:
            result = _deepseek(requested_model, messages, temperature, max_tokens, fallback)
        if result is None:
            continue
        attempted.append(candidate)
        duration_ms = round((time.monotonic() - started) * 1000)
        result["duration_ms"] = duration_ms
        record_runtime_event(
            provider=candidate,
            success=bool(result["success"]),
            duration_ms=duration_ms,
            error_type=result.get("error_type") or "",
            fallback=fallback,
        )
        if result["success"]:
            result["attempted_providers"] = tuple(attempted)
            return result
        failures.append({"provider": candidate, "error_type": result.get("error_type") or "provider_error"})
    return {
        "content": "A IA hospedada está temporariamente indisponível. Tente novamente em instantes.",
        "provider": "none",
        "requested_model": requested_model,
        "model": None,
        "fallback": bool(attempted),
        "success": False,
        "attempted_providers": tuple(attempted),
        "failures": tuple(failures),
    }


def chat(model: str, messages: list, temperature: float = 0.2, max_tokens=None) -> str:
    return chat_with_metadata(model, messages, temperature, max_tokens)["content"]


def local_available() -> bool:
    return healthcheck_dmr()
