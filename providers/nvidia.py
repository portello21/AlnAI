from __future__ import annotations

import httpx


def chat_nvidia(
    api_key: str,
    base_url: str,
    model: str,
    messages: list,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    timeout: float = 90.0,
) -> str:
    """Call an OpenAI-compatible NVIDIA NIM endpoint.

    This provider is optional and never performs a request without both an API
    key and an explicitly configured model name.
    """
    if not api_key:
        return "Erro: NVIDIA_API_KEY nao configurada."
    if not model:
        return "Erro: NVIDIA_MODEL nao configurado."

    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return "Erro: NVIDIA NIM nao retornou choices."
        content = str((choices[0].get("message") or {}).get("content") or "").strip()
        return content or "Erro: NVIDIA NIM retornou resposta vazia."
    except httpx.TimeoutException:
        return "Erro: timeout ao consultar NVIDIA NIM."
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        return f"Erro HTTP NVIDIA NIM: {code}."
    except Exception as exc:
        return f"Erro NVIDIA NIM: {type(exc).__name__}."
