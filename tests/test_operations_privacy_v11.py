from types import SimpleNamespace

import core.operations_store as store
from core.observability import _safe_properties


class Query:
    def __init__(self): self.payload = None
    def insert(self, payload): self.payload = payload; return self
    def execute(self): return SimpleNamespace(data=[self.payload])


class Client:
    def __init__(self): self.query = Query()
    def table(self, name): assert name == "rog_audit_events"; return self.query


def test_audit_and_product_properties_drop_private_content(monkeypatch):
    client = Client()
    monkeypatch.setattr(store, "_client", lambda: client)
    assert store.record_audit(event_type="chat.completed", outcome="success", user_id="id", profile="Allan", metadata={"provider": "nvidia", "prompt": "private", "answer": "secret"})
    assert client.query.payload["metadata"] == {"provider": "nvidia"}
    assert "prompt" not in _safe_properties({"prompt": "private", "provider": "nvidia"})
    assert "answer" not in _safe_properties({"answer": "secret", "success": True})
