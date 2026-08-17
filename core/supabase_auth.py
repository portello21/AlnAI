from __future__ import annotations

from dataclasses import dataclass
import base64
import json

from core.auth_v8 import normalize_profile
from core.config import Config
from core.supabase_optional import create_privileged_client, create_public_client


@dataclass(frozen=True)
class AuthIdentity:
    user_id: str
    profile: str
    access_token: str
    refresh_token: str = ""
    expires_at: int = 0
    aal: str = "aal1"
    is_admin: bool = False


def auth_available_for(profile: str) -> bool:
    return bool(
        Config.SUPABASE_AUTH_ENABLED
        and Config.SUPABASE_URL
        and Config.SUPABASE_PUBLISHABLE_KEY
        and Config.profile_auth_email(profile)
    )


def _confirm_active(identity: AuthIdentity | None) -> AuthIdentity | None:
    if identity is None:
        return None
    client = create_privileged_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)
    if client is None:
        return None
    try:
        response = (
            client.table("rog_user_profiles")
            .select("profile,role,active")
            .eq("user_id", identity.user_id)
            .eq("profile", identity.profile.casefold())
            .eq("active", True)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        if not rows:
            return None
        return AuthIdentity(
            user_id=identity.user_id,
            profile=identity.profile,
            access_token=identity.access_token,
            refresh_token=identity.refresh_token,
            expires_at=identity.expires_at,
            aal=identity.aal,
            is_admin=str(rows[0].get("role") or "member").casefold() == "admin",
        )
    except Exception:
        return None


def _identity_from_user(user, *, access_token: str, refresh_token: str = "", expires_at: int = 0) -> AuthIdentity | None:
    if user is None or bool(getattr(user, "is_anonymous", False)):
        return None
    metadata = getattr(user, "app_metadata", None) or {}
    profile = normalize_profile(metadata.get("rog_profile"))
    user_id = str(getattr(user, "id", "") or "")
    if not profile or not user_id:
        return None
    role = str(metadata.get("rog_role") or "member").casefold()
    aal = "aal1"
    try:
        segment = str(access_token).split(".")[1]
        segment += "=" * (-len(segment) % 4)
        claims = json.loads(base64.urlsafe_b64decode(segment).decode("utf-8"))
        if claims.get("aal") in {"aal1", "aal2"}:
            aal = claims["aal"]
    except Exception:
        pass
    return AuthIdentity(
        user_id=user_id,
        profile=profile,
        access_token=str(access_token or ""),
        refresh_token=str(refresh_token or ""),
        expires_at=int(expires_at or 0),
        aal=aal,
        is_admin=role == "admin",
    )


def sign_in_profile(profile: str, password: str) -> AuthIdentity | None:
    profile = normalize_profile(profile)
    if not profile or not password or not auth_available_for(profile):
        return None
    client = create_public_client(Config.SUPABASE_URL, Config.SUPABASE_PUBLISHABLE_KEY)
    if client is None:
        return None
    try:
        response = client.auth.sign_in_with_password({"email": Config.profile_auth_email(profile), "password": password})
        session = getattr(response, "session", None)
        identity = _identity_from_user(
            getattr(response, "user", None),
            access_token=getattr(session, "access_token", ""),
            refresh_token=getattr(session, "refresh_token", ""),
            expires_at=getattr(session, "expires_at", 0),
        )
        return _confirm_active(identity) if identity and identity.profile == profile else None
    except Exception:
        return None


def validate_access_token(token: str) -> AuthIdentity | None:
    token = str(token or "").strip()
    if not token:
        return None
    client = create_privileged_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)
    if client is None:
        return None
    try:
        response = client.auth.get_user(token)
        identity = _identity_from_user(getattr(response, "user", None), access_token=token)
        if identity is None:
            return None
        return _confirm_active(identity)
    except Exception:
        return None


def refresh_identity(refresh_token: str) -> AuthIdentity | None:
    client = create_public_client(Config.SUPABASE_URL, Config.SUPABASE_PUBLISHABLE_KEY)
    if client is None or not refresh_token:
        return None
    try:
        response = client.auth.refresh_session(str(refresh_token))
        session = getattr(response, "session", None)
        return _confirm_active(_identity_from_user(
            getattr(response, "user", None),
            access_token=getattr(session, "access_token", ""),
            refresh_token=getattr(session, "refresh_token", ""),
            expires_at=getattr(session, "expires_at", 0),
        ))
    except Exception:
        return None
