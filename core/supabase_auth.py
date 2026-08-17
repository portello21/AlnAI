from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import secrets
from urllib.parse import urljoin

import httpx

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
    password_change_required: bool = False


def auth_available_for(profile: str) -> bool:
    return bool(
        Config.SUPABASE_AUTH_ENABLED
        and Config.SUPABASE_URL
        and Config.SUPABASE_PUBLISHABLE_KEY
        and Config.profile_auth_email(profile)
    )


def _admin_headers(key: str) -> dict[str, str]:
    headers = {"apikey": key, "Accept": "application/json"}
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


def migrate_legacy_password(profile: str, password: str) -> bool:
    """Synchronize one verified legacy password to its exact Supabase user.

    The caller must verify the legacy password before invoking this function.
    Matching also requires immutable app_metadata for the requested profile,
    preventing an email configuration mistake from changing another account.
    """
    profile = normalize_profile(profile)
    email = Config.profile_auth_email(profile).strip().casefold() if profile else ""
    key = str(Config.SUPABASE_SERVICE_ROLE_KEY or "").strip()
    if not profile or not email or not password or not key:
        return False
    match = _admin_user_for_profile(profile)
    if match is None:
        return False
    user, headers = match
    try:
        update = httpx.put(
            urljoin(Config.SUPABASE_URL.rstrip("/") + "/", f"auth/v1/admin/users/{user['id']}"),
            headers={**headers, "Content-Type": "application/json"},
            json={"password": password},
            timeout=5.0,
        )
        update.raise_for_status()
        return True
    except Exception:
        return False


def _admin_user_for_profile(profile: str) -> tuple[dict, dict] | None:
    profile = normalize_profile(profile)
    email = Config.profile_auth_email(profile).strip().casefold() if profile else ""
    key = str(Config.SUPABASE_SERVICE_ROLE_KEY or "").strip()
    if not profile or not email or not key:
        return None
    headers = _admin_headers(key)
    try:
        response = httpx.get(
            urljoin(Config.SUPABASE_URL.rstrip("/") + "/", "auth/v1/admin/users"),
            headers=headers,
            params={"page": "1", "per_page": "1000"},
            timeout=5.0,
        )
        response.raise_for_status()
        payload = response.json()
        users = payload.get("users", []) if isinstance(payload, dict) else []
        matches = [
            user for user in users
            if isinstance(user, dict)
            and str(user.get("email") or "").strip().casefold() == email
            and normalize_profile((user.get("app_metadata") or {}).get("rog_profile")) == profile
        ]
        return (matches[0], headers) if len(matches) == 1 and matches[0].get("id") else None
    except Exception:
        return None


def generate_temporary_password(admin: AuthIdentity, target_profile: str) -> str:
    """Rotate one exact linked account after revalidating the admin session."""
    verified = validate_access_token(admin.access_token)
    if verified is None or verified.user_id != admin.user_id or not verified.is_admin:
        return ""
    match = _admin_user_for_profile(target_profile)
    if match is None:
        return ""
    user, headers = match
    temporary = secrets.token_urlsafe(15)
    metadata = dict(user.get("app_metadata") or {})
    metadata["rog_password_change_required"] = True
    try:
        response = httpx.put(
            urljoin(Config.SUPABASE_URL.rstrip("/") + "/", f"auth/v1/admin/users/{user['id']}"),
            headers={**headers, "Content-Type": "application/json"},
            json={"password": temporary, "app_metadata": metadata},
            timeout=5.0,
        )
        response.raise_for_status()
        return temporary
    except Exception:
        return ""


def complete_required_password_change(identity: AuthIdentity, new_password: str) -> bool:
    if len(str(new_password or "")) < 12:
        return False
    verified = validate_access_token(identity.access_token)
    if verified is None or verified.user_id != identity.user_id or verified.profile != identity.profile:
        return False
    match = _admin_user_for_profile(identity.profile)
    if match is None or str(match[0].get("id")) != identity.user_id:
        return False
    user, headers = match
    metadata = dict(user.get("app_metadata") or {})
    metadata["rog_password_change_required"] = False
    try:
        response = httpx.put(
            urljoin(Config.SUPABASE_URL.rstrip("/") + "/", f"auth/v1/admin/users/{identity.user_id}"),
            headers={**headers, "Content-Type": "application/json"},
            json={"password": str(new_password), "app_metadata": metadata},
            timeout=5.0,
        )
        response.raise_for_status()
        return True
    except Exception:
        return False


def _confirm_active(identity: AuthIdentity | None) -> AuthIdentity | None:
    if identity is None:
        return None
    key = str(Config.SUPABASE_SERVICE_ROLE_KEY or "").strip()
    try:
        if key.startswith("sb_secret_"):
            # Modern secret keys are not JWTs and must never be sent as a
            # Bearer token. A direct server-side PostgREST request with only
            # the apikey header preserves the secret-key bypass semantics.
            response = httpx.get(
                urljoin(Config.SUPABASE_URL.rstrip("/") + "/", "rest/v1/rog_user_profiles"),
                headers={"apikey": key, "Accept": "application/json"},
                params={
                    "select": "profile,role,active",
                    "user_id": f"eq.{identity.user_id}",
                    "profile": f"eq.{identity.profile.casefold()}",
                    "active": "eq.true",
                    "limit": "1",
                },
                timeout=3.0,
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload if isinstance(payload, list) else []
        else:
            client = create_privileged_client(Config.SUPABASE_URL, key)
            if client is None:
                return None
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
            password_change_required=identity.password_change_required,
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
        password_change_required=bool(metadata.get("rog_password_change_required")),
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
    client = create_public_client(Config.SUPABASE_URL, Config.SUPABASE_PUBLISHABLE_KEY)
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
