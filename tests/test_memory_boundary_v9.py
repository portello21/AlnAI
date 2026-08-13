from core.memory_service_v8 import FamilyMemoryService, SHARED_FINANCE_MEMORY_PROFILE


class FakeEngine:
    def __init__(self):
        self.rows = {
            "Allan": [{"id": "allan-1", "content": "private allan", "memory_type": "fact"}],
            "Beatriz": [{"id": "beatriz-1", "content": "private beatriz", "memory_type": "fact"}],
            "Natan": [{"id": "natan-1", "content": "private natan", "memory_type": "fact"}],
            "Tainan": [{"id": "tainan-1", "content": "private tainan", "memory_type": "fact"}],
            SHARED_FINANCE_MEMORY_PROFILE: [{"id": "shared-1", "content": "meta financeira do casal", "memory_type": "finance"}],
        }
        self.forgotten = []

    def list_memories(self, profile, active_only=True, limit=100):
        return list(self.rows.get(profile, []))[:limit]

    def search_memories(self, profile, query, limit=8):
        return list(self.rows.get(profile, []))[:limit]

    def forget_memory(self, memory_id):
        self.forgotten.append(memory_id)
        return True


def service():
    return FamilyMemoryService(engine=FakeEngine())


def test_shared_finance_target_is_only_available_to_couple_finance():
    svc = service()
    assert svc.command_profile("Allan", "finance", shared_finance=True) == SHARED_FINANCE_MEMORY_PROFILE
    assert svc.command_profile("Beatriz", "finance", shared_finance=True) == SHARED_FINANCE_MEMORY_PROFILE
    assert svc.command_profile("Natan", "finance", shared_finance=True) == "Natan"
    assert svc.command_profile("Tainan", "finance", shared_finance=True) == "Tainan"
    assert svc.command_profile("Allan", "personal", shared_finance=True) == "Allan"


def test_shared_finance_context_is_invisible_to_other_profiles_and_agents():
    svc = service()
    assert "meta financeira" in svc.shared_finance_context("Allan", "finance", "meta")
    assert "meta financeira" in svc.shared_finance_context("Beatriz", "finance", "meta")
    assert svc.shared_finance_context("Natan", "finance", "meta") == ""
    assert svc.shared_finance_context("Tainan", "finance", "meta") == ""
    assert svc.shared_finance_context("Allan", "personal", "meta") == ""
    assert svc.shared_finance_context("Beatriz", "document", "meta") == ""


def test_memory_idor_attempt_is_denied_before_delete():
    svc = service()
    assert not svc.forget_authorized("Natan", "personal", "allan-1")
    assert not svc.forget_authorized("Tainan", "finance", "shared-1", shared_finance=True)
    assert svc.engine.forgotten == []


def test_owner_can_delete_only_visible_memory():
    svc = service()
    assert svc.forget_authorized("Allan", "personal", "allan-1")
    assert svc.engine.forgotten == ["allan-1"]
