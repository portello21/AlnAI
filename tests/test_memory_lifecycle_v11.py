from datetime import datetime, timedelta, timezone

from core.memory_engine import MemoryEngine, memory_not_expired
from core.memory_service_v8 import FamilyMemoryService


def test_memory_expiration_is_fail_closed():
    now = datetime.now(timezone.utc)
    assert memory_not_expired({})
    assert memory_not_expired({"expires_at": (now + timedelta(days=1)).isoformat()}, now=now)
    assert not memory_not_expired({"expires_at": (now - timedelta(seconds=1)).isoformat()}, now=now)
    assert not memory_not_expired({"expires_at": "invalid"}, now=now)


def test_authorized_edit_replaces_only_owned_memory(tmp_path):
    engine = MemoryEngine(db_path=str(tmp_path / "memory.db"))
    engine.client = None
    service = FamilyMemoryService(engine)
    original = engine.add_memory("Allan", "Prefiro café", importance=0.5)
    assert not service.edit_authorized("Beatriz", "personal", original["id"], content="Prefiro chá", importance=0.8)
    assert service.edit_authorized("Allan", "personal", original["id"], content="Prefiro chá", importance=0.8, expires_in_days=30)
    active = service.list_authorized("Allan", "personal")
    assert len(active) == 1
    assert active[0]["content"] == "Prefiro chá"
    assert active[0]["importance"] == 0.8
    assert active[0]["metadata"]["expires_at"]
