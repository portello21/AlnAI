from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8-sig")
UI = (ROOT / "core" / "ui_v8.py").read_text(encoding="utf-8-sig")


def test_v8_design_system_exists():
    assert "FAMILY INTELLIGENCE" in UI
    assert "Natan" in UI
    assert "Tainan" in UI
    assert "rog-welcome" in UI


def test_no_fake_family_names_in_active_app():
    assert "Irmão 1" not in APP
    assert "Irmão 2" not in APP
    assert "Irmao 1" not in APP
    assert "Irmao 2" not in APP


def test_chat_has_runtime_pipeline_and_fallback():
    assert "execute_agent(" in APP
    assert "ask_llm_sync(" in APP
    assert "processed_events" in APP


def test_profile_namespace_guards_are_wired():
    assert "allowed_namespaces(" in APP
    assert "write_namespace(" in APP


def test_no_components_v2_generic_callback_regression():
    assert "on_change=lambda: None" not in APP
