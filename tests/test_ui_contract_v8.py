from core.ui_v8 import AGENT_META, PROFILE_LABELS


def test_family_names_are_real_names():
    assert PROFILE_LABELS == {
        "allan": "Allan",
        "beatriz": "Beatriz",
        "natan": "Natan",
        "tainan": "Tainan",
    }
    assert "Irmão 1" not in PROFILE_LABELS.values()
    assert "Irmão 2" not in PROFILE_LABELS.values()


def test_all_expected_agents_exist():
    assert set(AGENT_META) == {
        "orchestrator", "personal", "finance", "tech",
        "coach", "business", "english", "document",
    }


def test_agent_labels_are_unique():
    labels = [meta[1] for meta in AGENT_META.values()]
    assert len(labels) == len(set(labels))


def test_ui_accessibility_and_truthful_status_contract():
    from pathlib import Path

    ui = (Path(__file__).resolve().parents[1] / "core" / "ui_v8.py").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in ui
    assert "focus-visible" in ui
    assert "● Online" not in ui
    assert "busy: bool = False" in ui


def test_legacy_html_ui_is_not_active():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    assert not (root / "templates" / "index.html").exists()
    assert not (root / "static" / "style.css").exists()
