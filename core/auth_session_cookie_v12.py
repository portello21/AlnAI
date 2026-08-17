from __future__ import annotations

import base64
import hashlib
import json
import time

from cryptography.fernet import Fernet, InvalidToken

from core.auth_v8 import DEFAULT_DEVICE_TTL_DAYS, normalize_profile


def _fernet(signing_secret: str) -> Fernet | None:
    secret = str(signing_secret or "")
    if len(secret) < 32:
        return None
    key = base64.urlsafe_b64encode(hashlib.sha256(("rog-auth-v12:" + secret).encode("utf-8")).digest())
    return Fernet(key)


def seal_supabase_session(profile: str, refresh_token: str, signing_secret: str, *, now: int | None = None) -> str:
    profile = normalize_profile(profile)
    refresh_token = str(refresh_token or "").strip()
    cipher = _fernet(signing_secret)
    if not profile or not refresh_token or cipher is None:
        return ""
    issued_at = int(time.time() if now is None else now)
    payload = {
        "v": 1,
        "profile": profile,
        "refresh_token": refresh_token,
        "iat": issued_at,
        "exp": issued_at + DEFAULT_DEVICE_TTL_DAYS * 86400,
    }
    return cipher.encrypt(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii")


def open_supabase_session(token: str, signing_secret: str, *, now: int | None = None) -> tuple[str, str] | None:
    cipher = _fernet(signing_secret)
    if cipher is None or not token:
        return None
    try:
        payload = json.loads(cipher.decrypt(str(token).encode("ascii")).decode("utf-8"))
        current = int(time.time() if now is None else now)
        profile = normalize_profile(payload.get("profile"))
        refresh_token = str(payload.get("refresh_token") or "").strip()
        if payload.get("v") != 1 or not profile or not refresh_token:
            return None
        if int(payload.get("iat", 0)) <= 0 or int(payload.get("exp", 0)) <= current:
            return None
        return profile, refresh_token
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError):
        return None
