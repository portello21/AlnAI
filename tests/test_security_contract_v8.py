import pytest

from core.profile_access import (
    PRIVATE_PROFILES,
    allowed_namespaces,
    can_access_namespace,
    private_namespace,
    write_namespace,
)


@pytest.mark.parametrize("profile", ["guest", "admin", "brother1", "", None])
def test_unknown_profiles_fail_closed(profile):
    assert allowed_namespaces(profile, "personal") == ()
    with pytest.raises(ValueError):
        private_namespace(profile)


def test_namespace_injection_is_denied():
    for profile in PRIVATE_PROFILES:
        assert not can_access_namespace(profile, "personal", "profile:admin")
        assert not can_access_namespace(profile, "personal", "shared:allan_beatriz:finance")


def test_shared_finance_cannot_be_requested_by_other_agents():
    assert write_namespace("allan", "tech", shared_finance=True) == "profile:allan"
    assert write_namespace("beatriz", "documents", shared_finance=True) == "profile:beatriz"
    assert write_namespace("natan", "finance", shared_finance=True) == "profile:natan"
    assert write_namespace("tainan", "finance", shared_finance=True) == "profile:tainan"
