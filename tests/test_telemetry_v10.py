from core.telemetry import clear_runtime_events, record_runtime_event, runtime_snapshot


def test_runtime_telemetry_aggregates_without_content_or_identity():
    clear_runtime_events()
    record_runtime_event(provider="nvidia", success=True, duration_ms=120, fallback=False)
    record_runtime_event(provider="deepseek", success=False, duration_ms=80, error_type="timeout", fallback=True)
    snapshot = runtime_snapshot()
    assert snapshot["requests"] == 2
    assert snapshot["successes"] == 1
    assert snapshot["failures"] == 1
    assert snapshot["fallbacks"] == 1
    assert snapshot["average_duration_ms"] == 100
    assert snapshot["providers"] == {"nvidia": 1, "deepseek": 1}
    assert "prompt" not in snapshot
    assert "profile" not in snapshot
