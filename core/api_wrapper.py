import httpx
import asyncio
import logging

async def robust_deepseek_call(api_key: str, model: str, messages: list, timeout: float = 90.0, retries: int = 3) -> str:
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "temperature": 0.3}
    
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"].get("content", "").strip()
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            if attempt == retries - 1:
                return f"❌ Erro de rede após {retries} tentativas: {str(e)}"
            await asyncio.sleep(2 ** attempt)
        except Exception as e:
            return f"❌ Erro crítico na API: {str(e)}"
    return "❌ Falha crítica de comunicação."