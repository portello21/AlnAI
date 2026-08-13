import time

from core.auth_v8 import (
    ALLOWED_PROFILES,
    credential_version,
    issue_device_token,
    normalize_profile,
    verify_device_token,
    verify_password,
)

SECRET = "x" * 64


def test_real_family_profile_names_only():
    assert ALLOWED_PROFILES == ("Allan", "Beatriz", "Natan", "Tainan")
    assert normalize_profile("natan") == "Natan"
    assert normalize_profile("TAINAN") == "Tainan"
    assert normalize_profile("Irmao 1") == ""
    assert normalize_profile("Irmao 2") == ""


def test_password_verification_is_fail_closed():
    secrets_map = {"ALLAN_PASSWORD": "correct-horse"}
    assert verify_password("Allan", "correct-horse", secrets_map)
    assert not verify_password("Allan", "wrong", secrets_map)
    assert not verify_password("Natan", "anything", secrets_map)
    assert not verify_password("Unknown", "anything", secrets_map)


def test_device_token_round_trip():
    now = int(time.time())
    tag = credential_version(SECRET, "correct-horse")
    token = issue_device_token(
        "Allan",
        SECRET,
        ttl_days=90,
        device_id="browser-device-123",
        now=now,
        credential_tag=tag,
    )
    identity = verify_device_token(token, SECRET, now=now + 1, expected_credential_tag=tag)
    assert identity is not None
    assert identity.profile == "Allan"
    assert identity.device_id == "browser-device-123"


def test_password_rotation_invalidates_existing_device_token():
    now = int(time.time())
    old_tag = credential_version(SECRET, "old-password")
    new_tag = credential_version(SECRET, "new-password")
    token = issue_device_token("Beatriz", SECRET, now=now, credential_tag=old_tag)
    assert verify_device_token(token, SECRET, now=now + 1, expected_credential_tag=old_tag) is not None
    assert verify_device_token(token, SECRET, now=now + 1, expected_credential_tag=new_tag) is None


def test_tampered_token_is_rejected():
    token = issue_device_token("Beatriz", SECRET)
    payload, signature = token.split(".", 1)
    tampered = ("A" if payload[0] != "A" else "B") + payload[1:] + "." + signature
    assert verify_device_token(tampered, SECRET) is None


def test_wrong_secret_is_rejected():
    token = issue_device_token("Natan", SECRET)
    assert verify_device_token(token, "y" * 64) is None


def test_expired_token_is_rejected():
    now = int(time.time())
    token = issue_device_token("Tainan", SECRET, ttl_days=1, now=now)
    assert verify_device_token(token, SECRET, now=now + 2 * 86400) is None


def test_future_issued_token_is_rejected():
    now = int(time.time())
    token = issue_device_token("Allan", SECRET, now=now + 3600)
    assert verify_device_token(token, SECRET, now=now) is None


def test_short_signing_secret_is_rejected():
    try:
        issue_device_token("Allan", "short")
    except ValueError:
        pass
    else:
        raise AssertionError("short signing secret was accepted")
    assert verify_device_token("anything", "short") is None
