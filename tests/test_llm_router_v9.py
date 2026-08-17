import core.llm_router_v9 as router


def test_auto_order_prefers_hosted_nvidia_then_local_then_paid(monkeypatch):
    monkeypatch.setattr(router.Config, "PROVIDER_MODE", "auto")
    monkeypatch.setattr(router.Config, "IS_CLOUD", False)
    assert router.attempt_order("deepseek-reasoner") == ("nvidia", "local", "deepseek")


def test_nvidia_mode_keeps_local_and_paid_fallbacks(monkeypatch):
    monkeypatch.setattr(router.Config, "PROVIDER_MODE", "nvidia")
    monkeypatch.setattr(router.Config, "IS_CLOUD", False)
    assert router.attempt_order("auto") == ("nvidia", "local", "deepseek")


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
    monkeypatch.setattr(router.Config, "IS_CLOUD", False)
    monkeypatch.setattr(router, "chat_local", lambda *args, **kwargs: "Erro: secret provider detail")
    result = router.chat_with_metadata("auto", [])
    assert result["success"] is False
    assert "secret provider detail" not in result["content"]
    assert result["failures"][0]["error_type"] == "provider_error"


def test_cloud_only_attempts_hosted_nvidia_without_paid_consent(monkeypatch):
    monkeypatch.setattr(router.Config, "IS_CLOUD", True)
    monkeypatch.setattr(router.Config, "ALLOW_PAID_PROVIDERS", False)
    assert router.attempt_order("qwen3") == ("nvidia",)


def test_cloud_failure_is_short_and_does_not_probe_docker(monkeypatch):
    monkeypatch.setattr(router.Config, "IS_CLOUD", True)
    monkeypatch.setattr(router.Config, "ALLOW_PAID_PROVIDERS", False)
    monkeypatch.setattr(router.Config, "NVIDIA_API", "configured")
    monkeypatch.setattr(router.Config, "NVIDIA_MODEL", "nvidia/nemotron-3-nano-30b-a3b")
    monkeypatch.setattr(router, "chat_nvidia", lambda *args, **kwargs: "Erro: timeout ao consultar NVIDIA NIM.")
    monkeypatch.setattr(router, "healthcheck_dmr", lambda: (_ for _ in ()).throw(AssertionError("Docker probed")))
    router.HEALTH._health.clear()
    result = router.chat_with_metadata("qwen3", [])
    assert result["attempted_providers"] == ("nvidia",)
    assert result["content"] == "A IA hospedada está temporariamente indisponível. Tente novamente em instantes."
