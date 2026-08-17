from __future__ import annotations

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
