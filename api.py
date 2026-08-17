from __future__ import annotations

import json
import threading
import time
from typing import Annotated
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.agent_runtime import AGENTS, execute_agent
from core.api_auth import require_admin_identity, require_identity
from core.config import Config
from core.rate_limit import SlidingWindowRateLimiter
from core.observability import capture_product_event, init_error_monitoring
from core.operations_store import list_user_profiles, operations_summary, record_audit_async, record_usage_async, set_user_active
from core.response_jobs import cancel_response_job, consume_response_job, drain_response_tokens, response_job_status, start_response_job
from core.supabase_auth import AuthIdentity, refresh_identity, sign_in_profile

init_error_monitoring()
app = FastAPI(title="ROG AI API", version="1.0.0", docs_url=None, redoc_url=None)
RATE_LIMITER = SlidingWindowRateLimiter(Config.API_RATE_LIMIT_PER_MINUTE)
_REQUESTS: dict[str, str] = {}
_REQUEST_LOCK = threading.RLock()


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    content: str = Field(min_length=1, max_length=12_000)

    @field_validator("role")
    @classmethod
    def allowed_role(cls, value: str) -> str:
        if value not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        return value


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: str = "orchestrator"
    message: str = Field(min_length=1, max_length=12_000)
    history: list[ChatMessage] = Field(default_factory=list)

    @field_validator("agent_id")
    @classmethod
    def known_agent(cls, value: str) -> str:
        normalized = str(value or "").strip().casefold()
        if normalized not in AGENTS:
            raise ValueError("unknown agent")
        return normalized

    @field_validator("history")
    @classmethod
    def bounded_history(cls, value: list[ChatMessage]) -> list[ChatMessage]:
        if len(value) > Config.API_MAX_HISTORY_MESSAGES:
            raise ValueError("history limit exceeded")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=20, max_length=4096)


class UserStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: bool


Identity = Annotated[AuthIdentity, Depends(require_identity)]
AdminIdentity = Annotated[AuthIdentity, Depends(require_admin_identity)]


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "rog-ai-api", "version": app.version}


@app.post("/v1/auth/login")
def login(payload: LoginRequest) -> dict:
    allowed, _ = RATE_LIMITER.allow("login:" + payload.profile.casefold())
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    identity = sign_in_profile(payload.profile, payload.password)
    if identity is None:
        record_audit_async(event_type="auth.api_login", outcome="denied", profile=payload.profile, metadata={"auth_backend": "supabase"})
        raise HTTPException(status_code=401, detail="Invalid credentials")
    record_audit_async(event_type="auth.api_login", outcome="success", user_id=identity.user_id, profile=identity.profile, metadata={"auth_backend": "supabase"})
    return {"access_token": identity.access_token, "refresh_token": identity.refresh_token, "expires_at": identity.expires_at, "token_type": "bearer", "profile": identity.profile}


@app.post("/v1/auth/refresh")
def refresh(payload: RefreshRequest) -> dict:
    identity = refresh_identity(payload.refresh_token)
    if identity is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return {"access_token": identity.access_token, "refresh_token": identity.refresh_token, "expires_at": identity.expires_at, "token_type": "bearer", "profile": identity.profile}


@app.get("/v1/me")
def me(identity: Identity) -> dict:
    return {"profile": identity.profile, "is_admin": identity.is_admin, "aal": identity.aal}


@app.get("/v1/agents")
def agents(identity: Identity) -> dict:
    return {"agents": [{"id": key, "name": value.name, "description": value.instruction} for key, value in AGENTS.items()]}


@app.get("/v1/admin/summary")
def admin_summary(identity: AdminIdentity) -> dict:
    return operations_summary(days=7)


@app.get("/v1/admin/users")
def admin_users(identity: AdminIdentity) -> dict:
    return {"users": list_user_profiles()}


@app.patch("/v1/admin/users/{user_id}")
def admin_user_status(user_id: str, payload: UserStatusRequest, identity: AdminIdentity) -> dict:
    if user_id == identity.user_id and not payload.active:
        raise HTTPException(status_code=400, detail="Administrator cannot deactivate the current session")
    if not set_user_active(user_id=user_id, active=payload.active):
        raise HTTPException(status_code=404, detail="User not found")
    record_audit_async(event_type="admin.user_status", outcome="success", user_id=identity.user_id, profile=identity.profile, metadata={"reason": "activated" if payload.active else "deactivated"})
    return {"updated": True, "active": payload.active}


@app.post("/v1/chat/stream")
def chat_stream(payload: ChatRequest, identity: Identity):
    allowed, remaining = RATE_LIMITER.allow(identity.user_id)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    history = [item.model_dump() for item in payload.history]
    job_id = start_response_job(
        profile=identity.profile,
        agent_id=payload.agent_id,
        target=execute_agent,
        kwargs={"agent_id": payload.agent_id, "history": history, "user_query": payload.message, "profile": identity.profile},
        streaming=True,
    )
    with _REQUEST_LOCK:
        _REQUESTS[job_id] = identity.user_id

    def events():
        try:
            yield _sse("start", {"request_id": job_id, "remaining": remaining})
            last_heartbeat = time.monotonic()
            while True:
                status = response_job_status(job_id=job_id, profile=identity.profile, agent_id=payload.agent_id)
                chunk = drain_response_tokens(job_id=job_id, profile=identity.profile, agent_id=payload.agent_id)
                if chunk:
                    yield _sse("token", {"text": chunk})
                if status["state"] == "running":
                    if time.monotonic() - last_heartbeat >= 10:
                        yield _sse("heartbeat", {})
                        last_heartbeat = time.monotonic()
                    time.sleep(0.05)
                    continue
                final = consume_response_job(job_id=job_id, profile=identity.profile, agent_id=payload.agent_id)
                if final["state"] == "done" and isinstance(final.get("result"), dict):
                    result = final["result"]
                    record_usage_async(user_id=identity.user_id, profile=identity.profile, request_id=job_id, agent_id=payload.agent_id, result=result)
                    record_audit_async(event_type="chat.completed", outcome="success" if result.get("success") else "failure", user_id=identity.user_id, profile=identity.profile, metadata={"agent_id": payload.agent_id, "provider": result.get("provider"), "error_type": result.get("error_type")})
                    capture_product_event("chat_completed", user_id=identity.user_id, properties={"agent": payload.agent_id, "provider": result.get("provider"), "model": result.get("model"), "success": bool(result.get("success")), "duration_ms": result.get("duration_ms")})
                    yield _sse("done", {"request_id": job_id, "answer": result.get("answer", ""), "agent": result.get("selected_agent"), "provider": result.get("provider"), "model": result.get("model")})
                elif final["state"] == "cancelled":
                    yield _sse("cancelled", {"request_id": job_id})
                else:
                    yield _sse("error", {"request_id": job_id, "message": "Generation failed"})
                break
        except GeneratorExit:
            cancel_response_job(job_id=job_id, profile=identity.profile, agent_id=payload.agent_id)
            raise
        finally:
            with _REQUEST_LOCK:
                _REQUESTS.pop(job_id, None)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.delete("/v1/chat/{request_id}")
def cancel_chat(request_id: str, agent_id: str, identity: Identity) -> dict:
    if agent_id not in AGENTS:
        raise HTTPException(status_code=400, detail="Unknown agent")
    with _REQUEST_LOCK:
        owner = _REQUESTS.get(request_id)
    if owner != identity.user_id:
        raise HTTPException(status_code=404, detail="Request not found")
    cancelled = cancel_response_job(job_id=request_id, profile=identity.profile, agent_id=agent_id)
    if cancelled:
        record_audit_async(event_type="chat.cancelled", outcome="success", user_id=identity.user_id, profile=identity.profile, metadata={"agent_id": agent_id})
    return {"cancelled": bool(cancelled)}


app.mount("/app", StaticFiles(directory=str(Path(__file__).resolve().parent / "mobile"), html=True), name="mobile")
