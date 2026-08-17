from core.database import PersistenceManager


def _messages(topic: str) -> list[dict]:
    return [
        {"role": "user", "content": f"Planejar {topic}"},
        {"role": "assistant", "content": f"Plano privado para {topic}", "runtime": {"model": "test"}},
    ]


def test_conversation_archive_lifecycle_is_scoped(tmp_path):
    manager = PersistenceManager(db_path=str(tmp_path / "history.db"))
    manager.client = None
    archive_id = manager.archive_conversation(profile="Allan", agent_id="Finance", messages=_messages("orçamento"))

    assert archive_id
    assert manager.list_conversation_archives(profile="allan", agent_id="finance", search="ORÇAMENTO")[0]["id"] == archive_id
    assert manager.load_conversation_archive(profile="allan", agent_id="finance", archive_id=archive_id)[0]["content"] == "Planejar orçamento"
    assert manager.load_conversation_archive(profile="beatriz", agent_id="finance", archive_id=archive_id) == []
    assert manager.load_conversation_archive(profile="allan", agent_id="tech", archive_id=archive_id) == []
    assert not manager.delete_conversation_archive(profile="beatriz", agent_id="finance", archive_id=archive_id)
    assert manager.delete_conversation_archive(profile="allan", agent_id="finance", archive_id=archive_id)
    assert manager.load_conversation_archive(profile="allan", agent_id="finance", archive_id=archive_id) == []


def test_empty_or_invalid_conversation_is_not_archived(tmp_path):
    manager = PersistenceManager(db_path=str(tmp_path / "history.db"))
    manager.client = None
    assert manager.archive_conversation(profile="Allan", agent_id="finance", messages=[]) is None
    assert manager.archive_conversation(profile="Allan", agent_id="finance", messages=[{"role": "system", "content": "secret"}]) is None


def test_archive_limits_messages_and_ignores_untrusted_shapes(tmp_path):
    manager = PersistenceManager(db_path=str(tmp_path / "history.db"))
    manager.client = None
    messages = [{"role": "user", "content": str(index)} for index in range(130)] + ["bad", {"role": "tool", "content": "hidden"}]
    archive_id = manager.archive_conversation(profile="Allan", agent_id="personal", messages=messages)
    restored = manager.load_conversation_archive(profile="Allan", agent_id="personal", archive_id=archive_id)
    assert len(restored) == 118
    assert restored[0]["content"] == "12"
