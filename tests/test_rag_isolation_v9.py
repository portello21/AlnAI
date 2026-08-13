from core.vector_rag_v9 import make_chunk_id, namespace_where, normalize_namespaces, validate_ownership


def test_identical_file_hashes_do_not_collide_across_namespaces():
    file_hash = "abc123"
    allan = make_chunk_id(file_hash, "profile:allan", 0)
    natan = make_chunk_id(file_hash, "profile:natan", 0)
    shared = make_chunk_id(file_hash, "shared:allan_beatriz:finance", 0)
    assert len({allan, natan, shared}) == 3


def test_private_namespace_requires_matching_owner():
    assert validate_ownership("Allan", "personal", "profile:allan")
    assert not validate_ownership("Allan", "personal", "profile:beatriz")
    assert not validate_ownership("Natan", "finance", "profile:allan")
    assert not validate_ownership("Tainan", "document", "profile:natan")


def test_shared_finance_is_only_allan_or_beatriz_finance():
    shared = "shared:allan_beatriz:finance"
    assert validate_ownership("Allan", "finance", shared)
    assert validate_ownership("Beatriz", "finance", shared)
    assert not validate_ownership("Allan", "personal", shared)
    assert not validate_ownership("Beatriz", "document", shared)
    assert not validate_ownership("Natan", "finance", shared)
    assert not validate_ownership("Tainan", "finance", shared)


def test_unknown_or_empty_namespaces_fail_closed():
    assert not validate_ownership("Allan", "finance", "shared:unknown")
    assert not validate_ownership("Allan", "finance", "")
    assert namespace_where([]) is None


def test_namespace_filter_deduplicates_and_normalizes():
    allowed = normalize_namespaces(["PROFILE:ALLAN", "profile:allan", " profile:allan "])
    assert allowed == ("profile:allan",)
    assert namespace_where(allowed) == {"namespace": "profile:allan"}
