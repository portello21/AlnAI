from __future__ import annotations

import base64
import json

import httpx

try:
    from supabase import ClientOptions, create_client
except Exception:  # optional cloud/local integration
    ClientOptions = None
    create_client = None


def create_optional_client(url: str, key: str, *, timeout_seconds: float = 3.0):
    """Create a fail-fast Supabase client without making persistence mandatory."""
    if not create_client or not ClientOptions or not url or not key:
        return None
    timeout = httpx.Timeout(max(1.0, timeout_seconds), connect=min(2.0, max(1.0, timeout_seconds)))
    options = ClientOptions(
        auto_refresh_token=False,
        persist_session=False,
        postgrest_client_timeout=timeout,
        storage_client_timeout=max(1, int(timeout_seconds)),
        function_client_timeout=max(1, int(timeout_seconds)),
    )
    return create_client(url, key, options=options)


def is_privileged_server_key(key: str) -> bool:
    """Accept new secret keys or legacy JWTs whose signed claim says service_role."""
    value = str(key or "").strip()
    if value.startswith("sb_secret_"):
        return True
    if value.startswith(("sb_publishable_", "anon")):
        return False
    try:
        payload = value.split(".", 2)[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
        return claims.get("role") == "service_role"
    except Exception:
        return False


def create_privileged_client(url: str, key: str, *, timeout_seconds: float = 3.0):
    if not is_privileged_server_key(key):
        return None
    return create_optional_client(url, key, timeout_seconds=timeout_seconds)
