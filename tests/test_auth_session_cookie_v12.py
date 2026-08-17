from core.auth_session_cookie_v12 import open_supabase_session, seal_supabase_session


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
