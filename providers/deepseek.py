import httpx

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


def chat_deepseek(
    api_key: str,
    messages: list,
    model: str = "deepseek-chat",
    temperature: float = 0.2,
    max_tokens: int = 4096,
    timeout: float = 120.0,
) -> str:

    if not api_key:
        return "Erro: DEEPSEEK_API_KEY nao configurada."

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                DEEPSEEK_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json=payload,
            )

            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []

        if not choices:
            return "Erro: DeepSeek nao retornou choices."

        message = choices[0].get("message") or {}
        content = (message.get("content") or "").strip()

        if content:
            return content

        return "Erro: DeepSeek retornou resposta vazia."

    except httpx.TimeoutException:
        return "Erro: timeout ao consultar DeepSeek."

    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:1000]
        return f"Erro HTTP DeepSeek: {exc}. {body}"

    except Exception as exc:
        return f"Erro DeepSeek: {exc}"