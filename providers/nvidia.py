from __future__ import annotations

import json
import httpx


def chat_nvidia(
    api_key: str,
    base_url: str,
    model: str,
    messages: list,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    timeout: float = 20.0,
    on_token=None,
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
        "stream": on_token is not None,
    }
    try:
        limits = httpx.Limits(max_connections=4, max_keepalive_connections=2)
        request_timeout = httpx.Timeout(timeout, connect=min(5.0, timeout))
        with httpx.Client(timeout=request_timeout, limits=limits) as client:
            if on_token is not None:
                chunks = []
                with client.stream("POST", url, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if not raw or raw == "[DONE]":
                            continue
                        data = json.loads(raw)
                        choices = data.get("choices") or []
                        token = str((choices[0].get("delta") or {}).get("content") or "") if choices else ""
                        if token:
                            chunks.append(token)
                            on_token(token)
                content = "".join(chunks).strip()
                return content or "Erro: NVIDIA NIM retornou resposta vazia."
            response = client.post(url, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload)
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
