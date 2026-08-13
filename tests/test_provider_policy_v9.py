from core.provider_policy import CostClass, PROVIDERS, ProviderHealthRegistry, provider_allowed
from core.tool_registry import ToolRisk, ToolSpec


def test_paid_providers_fail_closed_by_default():
    assert not provider_allowed("openai", allow_paid=False)
    assert not provider_allowed("anthropic", allow_paid=False)
    assert not provider_allowed("deepseek", allow_paid=False)
    assert not provider_allowed("unknown-provider", allow_paid=True)


def test_local_and_free_providers_are_allowed_without_paid_flag():
    assert PROVIDERS["docker-model-runner"].cost is CostClass.LOCAL
    assert PROVIDERS["nvidia"].cost is CostClass.FREE
    assert provider_allowed("docker-model-runner", allow_paid=False)
    assert provider_allowed("nvidia", allow_paid=False)


def test_circuit_breaker_blocks_after_repeated_failures():
    health = ProviderHealthRegistry(failure_threshold=2, cooldown_seconds=30)
    assert health.can_attempt("nvidia")
    health.failure("nvidia", "timeout")
    assert health.can_attempt("nvidia")
    health.failure("nvidia", "timeout")
    assert not health.can_attempt("nvidia")
    health.success("nvidia")
    assert health.can_attempt("nvidia")


def test_rate_limit_blocks_immediately():
    health = ProviderHealthRegistry(failure_threshold=3, cooldown_seconds=30)
    health.failure("nvidia", "rate_limit", rate_limited=True)
    assert not health.can_attempt("nvidia")


def _tool(risk: ToolRisk) -> ToolSpec:
    return ToolSpec(
        name="sample",
        description="sample",
        category="test",
        handler=lambda args: {"ok": True},
        input_schema={"type": "object", "properties": {}},
        risk=risk,
    )


def test_sensitive_tool_classes_force_confirmation():
    for risk in (ToolRisk.SENSITIVE_WRITE, ToolRisk.DANGEROUS):
        spec = _tool(risk)
        assert spec.sensitive
        assert spec.requires_confirmation


def test_read_only_tool_does_not_force_write_confirmation():
    spec = _tool(ToolRisk.READ_ONLY)
    assert not spec.sensitive
    assert not spec.requires_confirmation
    assert "handler" not in spec.public_dict()
