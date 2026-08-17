from types import SimpleNamespace

from core.supabase_rag import delete_remote_document, fetch_remote_chunks, mirror_document


class Query:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def delete(self): self.calls.append(("delete",)); return self
    def select(self, fields): self.calls.append(("select", fields)); return self
    def eq(self, field, value): self.calls.append(("eq", field, value)); return self
    def in_(self, field, values): self.calls.append(("in", field, tuple(values))); return self
    def limit(self, value): self.calls.append(("limit", value)); return self
    def upsert(self, rows, on_conflict): self.calls.append(("upsert", rows, on_conflict)); return self
    def execute(self): return SimpleNamespace(data=self.rows)


class Client:
    def __init__(self, rows=None): self.query = Query(rows)
    def table(self, name): assert name == "document_chunks"; return self.query


def test_document_mirror_rejects_mixed_namespaces():
    rows = [
        {"namespace": "profile:allan", "file_hash": "x"},
        {"namespace": "profile:natan", "file_hash": "x"},
    ]
    assert not mirror_document(rows, client=Client())


def test_document_mirror_replaces_one_owned_document():
    rows = [{"namespace": "profile:allan", "file_hash": "x", "chunk_index": 0}]
    client = Client()
    assert mirror_document(rows, client=client)
    assert ("eq", "namespace", "profile:allan") in client.query.calls
    assert ("eq", "file_hash", "x") in client.query.calls
    assert any(call[0] == "upsert" and call[2] == "namespace,file_hash,chunk_index" for call in client.query.calls)


def test_remote_reads_filter_again_after_response():
    client = Client([
        {"namespace": "profile:allan", "content": "ok"},
        {"namespace": "profile:natan", "content": "deny"},
    ])
    assert fetch_remote_chunks(("profile:allan",), client=client) == [{"namespace": "profile:allan", "content": "ok"}]


def test_remote_delete_is_namespace_and_hash_scoped():
    client = Client()
    assert delete_remote_document("hash", "profile:allan", client=client)
    assert ("eq", "namespace", "profile:allan") in client.query.calls
    assert ("eq", "file_hash", "hash") in client.query.calls
