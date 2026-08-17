from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from core.config import Config
from core.supabase_auth import AuthIdentity, validate_access_token


def bearer_token(authorization: str | None) -> str:
    value = str(authorization or "").strip()
    if not value.lower().startswith("bearer "):
        return ""
    return value[7:].strip()


def require_identity(authorization: str | None = Header(default=None)) -> AuthIdentity:
    if not Config.API_ENABLED:
        raise HTTPException(status_code=503, detail="API disabled")
    identity = validate_access_token(bearer_token(authorization))
    if identity is None:
        raise HTTPException(status_code=401, detail="Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})
    return identity


def require_admin_identity(identity: AuthIdentity = Depends(require_identity)) -> AuthIdentity:
    if not identity.is_admin:
        raise HTTPException(status_code=403, detail="Administrator access required")
    if Config.ADMIN_REQUIRE_MFA and identity.aal != "aal2":
        raise HTTPException(status_code=403, detail="MFA assurance level 2 required")
    return identity
