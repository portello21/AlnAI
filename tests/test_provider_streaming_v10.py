import httpx

from providers.deepseek import chat_deepseek
from providers.nvidia import chat_nvidia


class _StreamResponse:
    status_code = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    def iter_lines(self):
        return iter([
            'data: {"choices":[{"delta":{"content":"Olá"}}]}',
            'data: {"choices":[{"delta":{"content":" mundo"}}]}',
            "data: [DONE]",
        ])


class _Client:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, *args, **kwargs):
        assert kwargs["json"]["stream"] is True
        return _StreamResponse()


def test_nvidia_stream_forwards_real_sse_tokens(monkeypatch):
    monkeypatch.setattr(httpx, "Client", _Client)
    tokens = []
    value = chat_nvidia("key", "https://example.test/v1", "model", [], on_token=tokens.append)
    assert value == "Olá mundo"
    assert tokens == ["Olá", " mundo"]


def test_deepseek_stream_forwards_real_sse_tokens(monkeypatch):
    monkeypatch.setattr(httpx, "Client", _Client)
    tokens = []
    value = chat_deepseek("key", [], on_token=tokens.append)
    assert value == "Olá mundo"
    assert tokens == ["Olá", " mundo"]
