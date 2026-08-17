import base64
import json
from types import SimpleNamespace

from core.supabase_auth import _identity_from_user
from core.supabase_optional import is_publishable_key


def _jwt(role: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode().rstrip("=")
    return f"x.{payload}.x"


def test_public_key_validation_separates_anon_from_service_role():
    assert is_publishable_key("sb_publishable_example")
    assert is_publishable_key(_jwt("anon"))
    assert not is_publishable_key(_jwt("service_role"))


def test_identity_uses_only_server_controlled_app_metadata():
    user = SimpleNamespace(id="user-1", is_anonymous=False, app_metadata={"rog_profile": "Allan", "rog_role": "admin"}, user_metadata={"rog_profile": "Natan"})
    identity = _identity_from_user(user, access_token="token")
    assert identity.profile == "Allan"
    assert identity.is_admin


def test_identity_rejects_unknown_profile_and_anonymous_users():
    unknown = SimpleNamespace(id="user-1", is_anonymous=False, app_metadata={"rog_profile": "Owner"})
    anonymous = SimpleNamespace(id="user-2", is_anonymous=True, app_metadata={"rog_profile": "Allan"})
    assert _identity_from_user(unknown, access_token="token") is None
    assert _identity_from_user(anonymous, access_token="token") is None
