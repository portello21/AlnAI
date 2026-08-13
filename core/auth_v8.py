from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass


ALLOWED_PROFILES = ("Allan", "Beatriz", "Natan", "Tainan")
TOKEN_VERSION = 1
DEFAULT_DEVICE_TTL_DAYS = 90


@dataclass(frozen=True)
class DeviceIdentity:
    profile: str
    device_id: str
    expires_at: int


def normalize_profile(value: str | None) -> str:
    raw = str(value or "").strip()
    for profile in ALLOWED_PROFILES:
        if raw.casefold() == profile.casefold():
            return profile
    return ""


def verify_password(profile: str, candidate: str, secrets_map) -> bool:
    profile = normalize_profile(profile)
    candidate = str(candidate or "")
    if not profile or not candidate:
        return False
    try:
        expected = str(secrets_map[f"{profile.upper()}_PASSWORD"])
    except Exception:
        return False
    return bool(expected) and hmac.compare_digest(candidate.encode(), expected.encode())


def _b64url(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64url(data: str) -> bytes:
    import base64
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def issue_device_token(profile: str, secret: str, *, ttl_days: int = DEFAULT_DEVICE_TTL_DAYS, device_id: str | None = None) -> str:
    profile = normalize_profile(profile)
    if not profile:
        raise ValueError("Perfil nao autorizado")
    if len(str(secret or "")) < 32:
        raise ValueError("DEVICE_COOKIE_SECRET deve possuir pelo menos 32 caracteres")
    now = int(time.time())
    payload = {
        "v": TOKEN_VERSION,
        "profile": profile,
        "device_id": device_id or secrets.token_urlsafe(18),
        "iat": now,
        "exp": now + int(ttl_days) * 86400,
    }
    encoded = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signature = hmac.new(str(secret).encode(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{_b64url(signature)}"


def verify_device_token(token: str, secret: str, *, now: int | None = None) -> DeviceIdentity | None:
    try:
        encoded, supplied = str(token).split(".", 1)
        expected = hmac.new(str(secret).encode(), encoded.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64url(supplied), expected):
            return None
        payload = json.loads(_unb64url(encoded).decode())
        if payload.get("v") != TOKEN_VERSION:
            return None
        profile = normalize_profile(payload.get("profile"))
        expires_at = int(payload.get("exp", 0))
        device_id = str(payload.get("device_id", ""))
        if not profile or not device_id or expires_at <= int(now or time.time()):
            return None
        return DeviceIdentity(profile=profile, device_id=device_id, expires_at=expires_at)
    except Exception:
        return None
