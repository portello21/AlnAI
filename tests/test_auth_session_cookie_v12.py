from core.auth_session_cookie_v12 import open_supabase_session, seal_supabase_session
from core.supabase_auth import AuthIdentity
import core.session_restore_v9 as session_restore


def test_supabase_refresh_cookie_is_encrypted_and_round_trips():
    secret = "s" * 64
    token = seal_supabase_session("Allan", "refresh-secret-value", secret, now=100)
    assert token
    assert "Allan" not in token
    assert "refresh-secret-value" not in token
    assert open_supabase_session(token, secret, now=101) == ("Allan", "refresh-secret-value")


def test_supabase_refresh_cookie_rejects_tampering_and_expiry():
    secret = "s" * 64
    token = seal_supabase_session("Beatriz", "refresh-token", secret, now=100)
    assert open_supabase_session(token + "tampered", secret, now=101) is None
    assert open_supabase_session(token, secret, now=100 + 91 * 86400) is None


def test_component_cookie_fallback_restores_and_rotates_supabase_session(monkeypatch):
    secret = "s" * 64
    token = seal_supabase_session("Allan", "old-refresh", secret)
    identity = AuthIdentity(
        user_id="user-1",
        profile="Allan",
        access_token="new-access",
        refresh_token="new-refresh",
        is_admin=True,
    )
    state = type("State", (), {})()
    monkeypatch.setattr(session_restore.st, "session_state", state)
    monkeypatch.setattr(session_restore, "refresh_identity", lambda refresh: identity if refresh == "old-refresh" else None)

    assert session_restore.restore_supabase_session_token(token, secret)
    assert state.authenticated is True
    assert state.auth_backend == "supabase"
    assert state.auth_refresh_token == "new-refresh"
    assert state.auth_cookie_refresh_required is True


def test_component_cookie_fallback_rejects_profile_mismatch(monkeypatch):
    secret = "s" * 64
    token = seal_supabase_session("Beatriz", "refresh", secret)
    wrong = AuthIdentity(user_id="user-1", profile="Allan", access_token="access", refresh_token="next")
    monkeypatch.setattr(session_restore, "refresh_identity", lambda refresh: wrong)
    assert not session_restore.restore_supabase_session_token(token, secret)
