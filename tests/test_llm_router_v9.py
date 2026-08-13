import core.llm_router_v9 as router


def test_auto_order_is_local_then_free_then_paid(monkeypatch):
    monkeypatch.setattr(router.Config, "PROVIDER_MODE", "auto")
    assert router.attempt_order("deepseek-reasoner") == ("local", "nvidia", "deepseek")


def test_paid_deepseek_is_not_attempted_when_guard_is_off(monkeypatch):
    monkeypatch.setattr(router.Config, "DEEPSEEK_API", "configured-but-not-consent")
    monkeypatch.setattr(router.Config, "ALLOW_PAID_PROVIDERS", False)
    called = {"value": False}

    def fake_deepseek(**kwargs):
        called["value"] = True
        return "should not run"

    monkeypatch.setattr(router, "chat_deepseek", fake_deepseek)
    result = router._deepseek("deepseek-chat", [], 0.2, 100, False)
    assert result is None
    assert called["value"] is False


def test_paid_deepseek_requires_explicit_guard(monkeypatch):
    monkeypatch.setattr(router.Config, "DEEPSEEK_API", "configured")
    monkeypatch.setattr(router.Config, "ALLOW_PAID_PROVIDERS", True)
    monkeypatch.setattr(router, "chat_deepseek", lambda **kwargs: "ok")
    result = router._deepseek("deepseek-chat", [], 0.2, 100, False)
    assert result is not None
    assert result["success"] is True
    assert result["provider"] == "deepseek"


def test_final_failure_does_not_expose_provider_response(monkeypatch):
    monkeypatch.setattr(router.Config, "PROVIDER_MODE", "local")
    monkeypatch.setattr(router, "chat_local", lambda *args, **kwargs: "Erro: secret provider detail")
    result = router.chat_with_metadata("auto", [])
    assert result["success"] is False
    assert "secret provider detail" not in result["content"]
    assert result["failures"][0]["error_type"] == "provider_error"
