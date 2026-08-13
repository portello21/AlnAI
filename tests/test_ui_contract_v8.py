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
