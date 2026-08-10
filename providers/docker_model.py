import httpx


DMR_URL = "http://127.0.0.1:12434/engines/v1/chat/completions"
DMR_MODELS_URL = "http://127.0.0.1:12434/engines/v1/models"
DMR_MODEL = "docker.io/ai/qwen3:latest"


def chat_dmr(
    messages: list,
    model: str = DMR_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    timeout: float = 180.0,
) -> str:

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:

        with httpx.Client(timeout=timeout) as client:

            response = client.post(
                DMR_URL,
                headers={
                    "Content-Type":
                    "application/json; charset=utf-8"
                },
                json=payload,
            )

            response.raise_for_status()

            data = response.json()

        choices = data.get("choices") or []

        if not choices:
            return (
                "Erro: Docker Model Runner "
                "nao retornou choices."
            )

        choice = choices[0] or {}
        message = choice.get("message") or {}

        content = (
            message.get("content") or ""
        ).strip()

        if content:
            return content

        reasoning = (
            message.get("reasoning_content") or ""
        ).strip()

        finish_reason = choice.get(
            "finish_reason"
        )

        if reasoning:

            if finish_reason == "length":
                return (
                    "Erro: Qwen3 consumiu o limite "
                    "de tokens durante o raciocinio "
                    "antes de produzir a resposta final."
                )

            return (
                "Erro: Qwen3 retornou raciocinio "
                "sem resposta final."
            )

        return "Erro: Qwen3 retornou resposta vazia."

    except httpx.TimeoutException:

        return (
            "Erro: timeout ao consultar "
            "Qwen3 local."
        )

    except httpx.HTTPStatusError as exc:

        body = exc.response.text[:1000]

        return (
            "Erro HTTP Docker Model Runner: "
            f"{exc}. {body}"
        )

    except Exception as exc:

        return (
            "Erro Docker Model Runner: "
            f"{exc}"
        )


def healthcheck_dmr(
    timeout: float = 10.0,
) -> bool:

    try:

        with httpx.Client(timeout=timeout) as client:

            response = client.get(
                DMR_MODELS_URL
            )

            response.raise_for_status()

            data = response.json()

        for model in data.get("data", []):

            model_id = str(
                model.get("id", "")
            ).lower()

            if "qwen3" in model_id:
                return True

        return False

    except Exception:
        return False
