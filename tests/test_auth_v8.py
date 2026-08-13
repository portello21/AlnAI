import time

from core.auth_v8 import ALLOWED_PROFILES, issue_device_token, normalize_profile, verify_device_token


SECRET = "x" * 64


def test_real_family_profile_names_only():
    assert ALLOWED_PROFILES == ("Allan", "Beatriz", "Natan", "Tainan")
    assert normalize_profile("natan") == "Natan"
    assert normalize_profile("tainan") == "Tainan"
    assert normalize_profile("Irmao 1") == ""
    assert normalize_profile("Irmao 2") == ""


def test_device_token_round_trip():
    token = issue_device_token("Allan", SECRET, ttl_days=90, device_id="browser-1")
    identity = verify_device_token(token, SECRET)
    assert identity is not None
    assert identity.profile == "Allan"
    assert identity.device_id == "browser-1"


def test_tampered_token_is_rejected():
    token = issue_device_token("Beatriz", SECRET)
    payload, signature = token.split(".", 1)
    tampered = ("A" if payload[0] != "A" else "B") + payload[1:] + "." + signature
    assert verify_device_token(tampered, SECRET) is None


def test_wrong_secret_is_rejected():
    token = issue_device_token("Natan", SECRET)
    assert verify_device_token(token, "y" * 64) is None


def test_expired_token_is_rejected():
    token = issue_device_token("Tainan", SECRET, ttl_days=1)
    assert verify_device_token(token, SECRET, now=int(time.time()) + 2 * 86400) is None
