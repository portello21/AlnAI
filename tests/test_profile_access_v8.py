from core.profile_access import allowed_namespaces, write_namespace, can_access_namespace


def test_private_profiles_are_isolated():
    profiles = ("allan", "beatriz", "natan", "tainan")
    for profile in profiles:
        allowed = allowed_namespaces(profile, "personal")
        assert allowed == (f"profile:{profile}",)
        for other in profiles:
            if other != profile:
                assert f"profile:{other}" not in allowed


def test_only_allan_and_beatriz_share_finance():
    shared = "shared:allan_beatriz:finance"
    assert shared in allowed_namespaces("allan", "finance")
    assert shared in allowed_namespaces("beatriz", "finance")
    assert shared not in allowed_namespaces("natan", "finance")
    assert shared not in allowed_namespaces("tainan", "finance")
    assert shared not in allowed_namespaces("allan", "personal")
    assert shared not in allowed_namespaces("beatriz", "tech")


def test_shared_finance_write_is_fail_closed():
    shared = "shared:allan_beatriz:finance"
    assert write_namespace("allan", "finance", shared_finance=True) == shared
    assert write_namespace("beatriz", "finance", shared_finance=True) == shared
    assert write_namespace("natan", "finance", shared_finance=True) == "profile:natan"
    assert write_namespace("tainan", "finance", shared_finance=True) == "profile:tainan"
    assert write_namespace("allan", "personal", shared_finance=True) == "profile:allan"


def test_cross_profile_namespace_access_is_denied():
    assert not can_access_namespace("natan", "personal", "profile:allan")
    assert not can_access_namespace("tainan", "finance", "shared:allan_beatriz:finance")
    assert not can_access_namespace("beatriz", "tech", "profile:allan")
