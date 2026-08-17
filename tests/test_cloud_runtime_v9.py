from core.supabase_optional import create_optional_client


def test_supabase_is_optional_without_configuration():
    assert create_optional_client("", "") is None


def test_trusted_cookie_uses_secure_browser_attributes(monkeypatch):
    import core.login_v9 as login

    calls = []

    class Manager:
        def set(self, *args, **kwargs):
            calls.append((args, kwargs))

    monkeypatch.setattr(login, "_cookie_secret", lambda: "x" * 64)
    monkeypatch.setattr(login, "_credential_tag", lambda profile: "tag")
    monkeypatch.setattr(login.time, "sleep", lambda seconds: None)
    assert login._persist_trusted_device(Manager(), "Allan")
    assert calls[0][0][0] == "rog_ai_device"
    assert calls[0][1]["path"] == "/"
    assert calls[0][1]["secure"] is True
    assert calls[0][1]["same_site"] == "strict"
