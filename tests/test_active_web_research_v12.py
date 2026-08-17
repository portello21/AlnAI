from types import SimpleNamespace

import core.agent_runtime as runtime
from core.research_engine import ResearchResponse, ResearchResult


def _response(success=True):
    results = (
        ResearchResult(rank=1, title="Fonte confiável", url="https://example.com/noticia", snippet="Fato atual.", domain="example.com"),
    ) if success else ()
    return ResearchResponse(success=success, query="consulta", results=results, error=None if success else "offline")


def test_explicit_and_current_requests_trigger_web_but_private_queries_do_not():
    assert runtime.should_search_web("Pesquise na internet as notícias atuais sobre IA")
    assert runtime.should_search_web("Qual é a cotação atual do dólar?")
    assert not runtime.should_search_web("Explique recursão em Python")
    assert not runtime.should_search_web("Organize meu dia hoje")
    assert not runtime.should_search_web("Pesquise na web a senha allan@example.com")


def test_web_context_contains_numbered_untrusted_evidence(monkeypatch):
    monkeypatch.setattr(runtime.research_engine, "search", lambda **kwargs: _response())
    result = runtime.build_web_context("Pesquise na internet uma notícia atual")
    assert result["success"] is True
    assert "dados externos não confiáveis" in result["text"]
    assert "[1] Fonte confiável" in result["text"]
    assert result["sources"][0]["url"] == "https://example.com/noticia"


def test_web_failure_is_safe_and_does_not_invent_sources(monkeypatch):
    monkeypatch.setattr(runtime.research_engine, "search", lambda **kwargs: _response(False))
    result = runtime.build_web_context("Pesquise na web as notícias atuais")
    assert result == {"attempted": True, "success": False, "sources": [], "text": "", "error": "offline"}
    answer = runtime.append_web_sources("Conhecimento geral.", result)
    assert "pesquisa web não ficou disponível" in answer
    assert "pode não estar atualizada" in answer
    assert "Fontes consultadas" not in answer


def test_sources_are_appended_to_model_answer():
    answer = runtime.append_web_sources("Resposta com evidência [1].", {
        "success": True,
        "sources": [{"title": "Fonte confiável", "domain": "example.com", "url": "https://example.com/noticia"}],
    })
    assert "### Fontes consultadas" in answer
    assert "[Fonte confiável](https://example.com/noticia)" in answer


def test_active_execute_agent_uses_web_results(monkeypatch):
    monkeypatch.setattr(runtime.research_engine, "search", lambda **kwargs: _response())
    monkeypatch.setattr(runtime, "build_memory_context", lambda **kwargs: {
        "text": "", "context_count": 0, "context_ids": [], "retrieved_count": 0,
        "retrieved_ids": [], "context_chars": 0, "budget_chars": 4000,
        "context_truncated": False,
    })
    monkeypatch.setattr(runtime._model_router, "decide", lambda **kwargs: SimpleNamespace(
        selected_model="test-model", requested_model="test-model", route_mode="test",
        reason="test", complexity_score=0, reasoning_score=0, privacy_score=0,
        local_available=False,
    ))
    monkeypatch.setattr(runtime, "chat_with_metadata", lambda **kwargs: {
        "content": "Resposta fundamentada [1].", "success": False, "model": "test-model", "provider": "test",
    })

    result = runtime.execute_agent(
        agent_id="orchestrator", history=[], user_query="Pesquise na internet as notícias atuais de IA", profile="Allan",
    )

    assert result["web_search_attempted"] is True
    assert result["web_search_success"] is True
    assert result["web_sources"][0]["domain"] == "example.com"
    assert "### Fontes consultadas" in result["answer"]
