from core.tool_registry import ToolRisk, ToolSpec


def handler(args):
    return {"ok": True}


def make_spec(risk):
    return ToolSpec(
        name="sample",
        description="sample",
        category="test",
        handler=handler,
        input_schema={"type": "object", "properties": {}},
        risk=risk,
    )


def test_read_only_is_not_forced_to_confirm():
    spec = make_spec(ToolRisk.READ_ONLY)
    assert not spec.sensitive
    assert not spec.requires_confirmation


def test_sensitive_write_requires_confirmation():
    spec = make_spec(ToolRisk.SENSITIVE_WRITE)
    assert spec.sensitive
    assert spec.requires_confirmation


def test_high_risk_write_requires_confirmation():
    spec = make_spec(ToolRisk.DANGEROUS)
    assert spec.sensitive
    assert spec.requires_confirmation


def test_handler_is_not_exposed_publicly():
    public = make_spec(ToolRisk.READ_ONLY).public_dict()
    assert "handler" not in public
