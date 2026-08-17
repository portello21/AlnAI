import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import api
from core.api_auth import require_identity
from core.supabase_auth import AuthIdentity


def _identity():
    return AuthIdentity(user_id="user-1", profile="Allan", access_token="token", is_admin=True)


def test_health_is_public_but_identity_routes_are_protected():
    client = TestClient(api.app)
    assert client.get("/health").status_code == 200
    assert client.get("/v1/me").status_code == 401


def test_authenticated_api_exposes_identity_and_real_agents():
    api.app.dependency_overrides[require_identity] = _identity
    try:
        client = TestClient(api.app)
        assert client.get("/v1/me").json() == {"profile": "Allan", "is_admin": True, "aal": "aal1"}
        agents = client.get("/v1/agents").json()["agents"]
        assert {item["id"] for item in agents} == set(api.AGENTS)
        response = client.post("/v1/chat/stream", json={"agent_id": "unknown", "message": "teste"})
        assert response.status_code == 422
    finally:
        api.app.dependency_overrides.clear()
