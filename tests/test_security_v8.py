from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8-sig")
PROFILE_ACCESS = (ROOT / "core" / "profile_access.py").read_text(encoding="utf-8-sig")


def test_profiles_use_real_names():
    for name in ("Allan", "Beatriz", "Natan", "Tainan"):
        assert f'"{name}"' in APP
    assert "Irmao 1" not in APP
    assert "Irmao 2" not in APP
    assert "Irmão 1" not in APP
    assert "Irmão 2" not in APP


def test_identity_is_not_accepted_from_query_string():
    assert '"auth" in st.query_params' in APP
    assert 'del st.query_params["auth"]' in APP


def test_password_comparison_is_constant_time():
    assert "hmac.compare_digest" in APP


def test_profile_access_is_fail_closed():
    assert "if profile not in PRIVATE_PROFILES" in PROFILE_ACCESS
    assert "return ()" in PROFILE_ACCESS


def test_no_plaintext_password_literals_in_app():
    banned = ("SkullAngel", "@Pass", "password = \"")
    for item in banned:
        assert item not in APP
