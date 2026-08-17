from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "api.py").read_text(encoding="utf-8")
SW = (ROOT / "mobile" / "sw.js").read_text(encoding="utf-8")
APP = (ROOT / "mobile" / "app.js").read_text(encoding="utf-8")


def test_api_requires_identity_and_bounds_inputs():
    assert 'Depends(require_identity)' in API
    assert 'max_length=12_000' in API
    assert 'API_MAX_HISTORY_MESSAGES' in API
    assert 'SlidingWindowRateLimiter' in API


def test_mobile_cache_never_caches_private_api_responses():
    assert 'url.pathname.startsWith("/v1/")' in SW
    assert 'cache:"no-store"' in APP
    assert 'localStorage' not in APP
    assert 'sessionStorage' in APP


def test_api_has_agent_stream_cancel_and_auth_contracts():
    for route in ('/v1/auth/login', '/v1/auth/refresh', '/v1/agents', '/v1/chat/stream', '/v1/chat/{request_id}'):
        assert route in API
