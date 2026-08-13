from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8-sig")
SHELL = (ROOT / "core" / "app_shell_v8.py").read_text(encoding="utf-8-sig")
AUTH = (ROOT / "core" / "auth_v8.py").read_text(encoding="utf-8-sig")
PROFILE_ACCESS = (ROOT / "core" / "profile_access.py").read_text(encoding="utf-8-sig")
GITIGNORE = (ROOT / ".gitignore").read_text(encoding="utf-8-sig")


def test_profiles_use_real_names_only():
    for name in ("Allan", "Beatriz", "Natan", "Tainan"):
        assert f'"{name}"' in AUTH
    for fake in ("Irmao 1", "Irmao 2", "Irmão 1", "Irmão 2", "Brother 1", "Brother 2"):
        assert fake not in APP + SHELL + AUTH


def test_authentication_is_not_accepted_from_query_string():
    assert "query_params" not in AUTH
    assert "query_params" not in SHELL


def test_password_and_token_comparisons_are_constant_time():
    assert "hmac.compare_digest" in AUTH


def test_profile_access_is_fail_closed():
    assert "if profile not in PRIVATE_PROFILES" in PROFILE_ACCESS
    assert "return ()" in PROFILE_ACCESS


def test_no_plaintext_password_literals_in_active_auth_code():
    banned = ("SkullAngel", "@Pass", 'password = "', "DEEPSEEK_API_KEY =")
    active = APP + SHELL + AUTH
    for item in banned:
        assert item not in active


def test_secret_files_and_local_databases_are_ignored():
    assert ".streamlit/secrets.toml" in GITIGNORE
    assert "*.db" in GITIGNORE
    assert ".env" in GITIGNORE


def test_device_token_has_expiry_and_hmac_signature():
    assert '"exp"' in AUTH
    assert "hashlib.sha256" in AUTH
    assert "DEVICE_COOKIE_SECRET" in AUTH
