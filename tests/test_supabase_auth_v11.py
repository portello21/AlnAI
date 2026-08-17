import base64
import json
from types import SimpleNamespace

import core.supabase_auth as supabase_auth
from core.supabase_auth import AuthIdentity, _confirm_active, _identity_from_user, complete_required_password_change, generate_temporary_password, migrate_legacy_password
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


def test_temporary_password_requires_revalidated_admin(monkeypatch):
    admin = AuthIdentity(user_id="admin-1", profile="Allan", access_token="token", is_admin=True)
    monkeypatch.setattr(supabase_auth, "validate_access_token", lambda token: None)
    monkeypatch.setattr(supabase_auth, "_admin_user_for_profile", lambda profile: (_ for _ in ()).throw(AssertionError("must not look up target")))
    assert generate_temporary_password(admin, "Beatriz") == ""


def test_temporary_password_marks_exact_user_for_first_access_change(monkeypatch):
    admin = AuthIdentity(user_id="admin-1", profile="Allan", access_token="token", is_admin=True)
    monkeypatch.setattr(supabase_auth, "validate_access_token", lambda token: admin)
    monkeypatch.setattr(supabase_auth, "_admin_user_for_profile", lambda profile: (
        {"id": "user-2", "app_metadata": {"rog_profile": "Beatriz", "rog_role": "member"}},
        {"apikey": "secret"},
    ))
    monkeypatch.setattr(supabase_auth.secrets, "token_urlsafe", lambda size: "temporary-password")
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

    def fake_put(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr(supabase_auth.httpx, "put", fake_put)
    class Query:
        def update(self, payload):
            captured["profile_update"] = payload
            return self
        def eq(self, key, value): return self
        def execute(self): return SimpleNamespace(data=[{"user_id": "user-2"}])
    monkeypatch.setattr(supabase_auth, "create_privileged_client", lambda *args: SimpleNamespace(table=lambda name: Query()))
    assert generate_temporary_password(admin, "Beatriz") == "temporary-password"
    assert captured["url"].endswith("/auth/v1/admin/users/user-2")
    assert captured["json"]["app_metadata"]["rog_password_change_required"] is True
    assert captured["profile_update"]["password_change_required"] is True


def test_password_change_uses_authenticated_user_session(monkeypatch):
    identity = AuthIdentity(user_id="user-1", profile="Allan", access_token="access", refresh_token="refresh")
    monkeypatch.setattr(supabase_auth, "validate_access_token", lambda token: identity)
    calls = []

    class Auth:
        def set_session(self, access, refresh):
            calls.append(("session", access, refresh))

        def update_user(self, payload):
            calls.append(("update", payload))
            return SimpleNamespace(user=SimpleNamespace(id="user-1"))

    monkeypatch.setattr(supabase_auth, "create_public_client", lambda *args: SimpleNamespace(auth=Auth()))
    class PatchResponse:
        def raise_for_status(self): return None
        def json(self): return [{"user_id": "user-1"}]
    monkeypatch.setattr(supabase_auth.httpx, "patch", lambda *args, **kwargs: PatchResponse())
    assert complete_required_password_change(identity, "a-secure-new-password")
    assert calls == [("session", "access", "refresh"), ("update", {"password": "a-secure-new-password"})]


def test_active_profile_check_uses_user_jwt_and_publishable_key(monkeypatch):
    monkeypatch.setattr(supabase_auth.Config, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(supabase_auth.Config, "SUPABASE_PUBLISHABLE_KEY", "sb_publishable_client")
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"profile": "allan", "role": "admin", "active": True, "password_change_required": True}]

    def fake_get(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return Response()

    monkeypatch.setattr(supabase_auth.httpx, "get", fake_get)
    identity = AuthIdentity(user_id="user-1", profile="Allan", access_token="user-jwt")

    confirmed = _confirm_active(identity)

    assert confirmed is not None and confirmed.is_admin and confirmed.password_change_required
    assert captured["headers"]["apikey"] == "sb_publishable_client"
    assert captured["headers"]["Authorization"] == "Bearer user-jwt"
    assert captured["params"]["profile"] == "eq.allan"


def test_legacy_password_migration_updates_only_exact_metadata_match(monkeypatch):
    monkeypatch.setattr(supabase_auth.Config, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(supabase_auth.Config, "SUPABASE_SERVICE_ROLE_KEY", "sb_secret_server")
    monkeypatch.setattr(supabase_auth.Config, "profile_auth_email", lambda profile: "allan@example.test")
    calls = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    monkeypatch.setattr(supabase_auth.httpx, "get", lambda *args, **kwargs: Response({"users": [
        {"id": "user-1", "email": "allan@example.test", "app_metadata": {"rog_profile": "allan", "rog_role": "admin"}},
        {"id": "user-2", "email": "other@example.test", "app_metadata": {"rog_profile": "beatriz"}},
    ]}))

    def fake_put(url, **kwargs):
        calls.append((url, kwargs))
        return Response({"id": "user-1"})

    monkeypatch.setattr(supabase_auth.httpx, "put", fake_put)

    assert migrate_legacy_password("Allan", "new-secret")
    assert len(calls) == 1
    assert calls[0][0].endswith("/auth/v1/admin/users/user-1")
    assert calls[0][1]["json"] == {"password": "new-secret"}
    assert calls[0][1]["headers"]["apikey"] == "sb_secret_server"
    assert "Authorization" not in calls[0][1]["headers"]


def test_legacy_password_migration_refuses_email_without_matching_profile(monkeypatch):
    monkeypatch.setattr(supabase_auth.Config, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(supabase_auth.Config, "SUPABASE_SERVICE_ROLE_KEY", "sb_secret_server")
    monkeypatch.setattr(supabase_auth.Config, "profile_auth_email", lambda profile: "allan@example.test")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"users": [{"id": "wrong", "email": "allan@example.test", "app_metadata": {"rog_profile": "beatriz"}}]}

    monkeypatch.setattr(supabase_auth.httpx, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(supabase_auth.httpx, "put", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not update")))

    assert not migrate_legacy_password("Allan", "new-secret")

