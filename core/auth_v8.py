from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Mapping

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
        if hmac.compare_digest(raw.casefold(), profile.casefold()):
            return profile
    return ""


def verify_password(profile: str, candidate: str, secrets_map: Mapping[str, object]) -> bool:
    profile = normalize_profile(profile)
    candidate = str(candidate or "")
    if not profile or not candidate:
        return False
    try:
        expected = str(secrets_map[f"{profile.upper()}_PASSWORD"])
    except Exception:
        return False
    return bool(expected) and hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64url(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def issue_device_token(profile: str, secret: str, *, ttl_days: int = DEFAULT_DEVICE_TTL_DAYS, device_id: str | None = None, now: int | None = None) -> str:
    profile = normalize_profile(profile)
    secret = str(secret or "")
    if not profile:
        raise ValueError("Perfil nao autorizado")
    if len(secret) < 32:
        raise ValueError("DEVICE_COOKIE_SECRET deve possuir pelo menos 32 caracteres")
    issued = int(time.time() if now is None else now)
    payload = {
        "v": TOKEN_VERSION,
        "profile": profile,
        "device_id": device_id or secrets.token_urlsafe(18),
        "iat": issued,
        "exp": issued + max(1, int(ttl_days)) * 86400,
    }
    encoded = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64url(signature)}"


def verify_device_token(token: str, secret: str, *, now: int | None = None) -> DeviceIdentity | None:
    secret = str(secret or "")
    if len(secret) < 32:
        return None
    try:
        encoded, supplied = str(token or "").split(".", 1)
        expected = hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
        supplied_bytes = _unb64url(supplied)
        if not hmac.compare_digest(supplied_bytes, expected):
            return None
        payload = json.loads(_unb64url(encoded).decode("utf-8"))
        if payload.get("v") != TOKEN_VERSION:
            return None
        profile = normalize_profile(payload.get("profile"))
        issued_at = int(payload.get("iat", 0))
        expires_at = int(payload.get("exp", 0))
        device_id = str(payload.get("device_id", ""))
        current = int(time.time() if now is None else now)
        if not profile or len(device_id) < 8:
            return None
        if issued_at <= 0 or issued_at > current + 300:
            return None
        if expires_at <= current or expires_at <= issued_at:
            return None
        return DeviceIdentity(profile=profile, device_id=device_id, expires_at=expires_at)
    except Exception:
        return None
