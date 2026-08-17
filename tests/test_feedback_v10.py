import hashlib
import sqlite3

from core.database import PersistenceManager


def test_feedback_stores_hash_not_response_content(tmp_path, monkeypatch):
    manager = PersistenceManager(db_path=str(tmp_path / "feedback.db"))
    manager.client = None
    content = "Resposta privada que não deve ir para a telemetria."
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert manager.save_feedback(profile="Allan", agent_id="finance", message_hash=digest, rating=-1, reason="Incompleta")
    with sqlite3.connect(manager.db) as conn:
        row = conn.execute("SELECT profile, message_hash, rating, reason FROM response_feedback").fetchone()
        raw = " ".join(str(value) for value in row)
    assert row == ("allan", digest, -1, "Incompleta")
    assert content not in raw


def test_feedback_rejects_invalid_identity_hash_or_rating(tmp_path):
    manager = PersistenceManager(db_path=str(tmp_path / "feedback.db"))
    manager.client = None
    assert not manager.save_feedback(profile="", agent_id="finance", message_hash="a" * 64, rating=1)
    assert not manager.save_feedback(profile="Allan", agent_id="", message_hash="a" * 64, rating=1)
    assert not manager.save_feedback(profile="Allan", agent_id="finance", message_hash="bad", rating=1)
    assert not manager.save_feedback(profile="Allan", agent_id="finance", message_hash="a" * 64, rating=0)
