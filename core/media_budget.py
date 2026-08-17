from __future__ import annotations

import hashlib
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.config import Config
from core.supabase_optional import create_privileged_client


MEDIA_ESTIMATES = {"image": 0.02, "video": 0.40}
_BUDGET_LOCK = threading.Lock()


def _client():
    return create_privileged_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)


def reserve_media(*, user_id: str, profile: str, media_type: str, prompt: str, provider: str, model: str) -> dict:
    if media_type not in MEDIA_ESTIMATES or not user_id or not prompt.strip():
        return {"success": False, "reason": "invalid_request"}
    client = _client()
    if client is None:
        return {"success": False, "reason": "budget_store_unavailable"}
    record = {
        "id": str(uuid4()), "user_id": user_id, "profile": profile.casefold(), "media_type": media_type,
        "provider": provider, "model": model, "status": "reserved",
        "estimated_cost_usd": MEDIA_ESTIMATES[media_type],
        "prompt_hash": hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest(),
    }
    try:
        with _BUDGET_LOCK:
            stale_before = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
            client.table("rog_media_usage").update({"status": "failed", "error_type": "reservation_expired", "completed_at": datetime.now(timezone.utc).isoformat()}).eq("status", "reserved").lt("created_at", stale_before).execute()
            settings = client.table("rog_budget_settings").select("*").eq("id", True).single().execute().data or {}
            quota = client.table("rog_profile_quotas").select("*").eq("profile", profile.casefold()).single().execute().data or {}
            if not settings.get("paid_media_enabled"):
                return {"success": False, "reason": "paid_media_disabled"}
            if not quota.get(f"{media_type}_enabled"):
                return {"success": False, "reason": f"{media_type}_disabled"}
            now = datetime.now(timezone.utc)
            month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
            day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            rows = client.table("rog_media_usage").select("profile,media_type,status,estimated_cost_usd,created_at").gte("created_at", month).execute().data or []
            active = [row for row in rows if row.get("status") in {"reserved", "completed"}]
            estimate = MEDIA_ESTIMATES[media_type]
            checks = ((sum(float(r.get("estimated_cost_usd") or 0) for r in active), float(settings.get("monthly_limit_usd", 10)), "monthly_budget_exceeded"), (sum(float(r.get("estimated_cost_usd") or 0) for r in active if str(r.get("created_at") or "") >= day), float(settings.get("daily_limit_usd", 1)), "daily_budget_exceeded"), (sum(float(r.get("estimated_cost_usd") or 0) for r in active if r.get("media_type") == media_type), float(settings.get(f"{media_type}_limit_usd", 0)), "media_budget_exceeded"), (sum(float(r.get("estimated_cost_usd") or 0) for r in active if r.get("profile") == profile.casefold()), float(quota.get("monthly_limit_usd", 0)), "profile_budget_exceeded"))
            for used, limit, reason in checks:
                if used + estimate > limit:
                    return {"success": False, "reason": reason}
            response = client.table("rog_media_usage").insert(record).execute()
            return {"success": bool(getattr(response, "data", None)), **record}
    except Exception as exc:
        message = str(exc).casefold()
        reason = next((key for key in ("paid_media_disabled", "monthly_budget_exceeded", "daily_budget_exceeded", "media_budget_exceeded", "profile_budget_exceeded", "image_disabled", "video_disabled") if key in message), "budget_rejected")
        return {"success": False, "reason": reason}


def finish_media(reservation_id: str, *, success: bool, actual_cost_usd: float | None = None, storage_path: str = "", error_type: str = "") -> bool:
    client = _client()
    if client is None or not reservation_id:
        return False
    payload = {"status": "completed" if success else "failed", "completed_at": datetime.now(timezone.utc).isoformat(), "storage_path": storage_path or None, "error_type": error_type[:80] or None}
    if success and actual_cost_usd is not None:
        payload["actual_cost_usd"] = max(0, float(actual_cost_usd))
    try:
        response = client.table("rog_media_usage").update(payload).eq("id", reservation_id).execute()
        return bool(getattr(response, "data", None))
    except Exception:
        return False


def budget_snapshot() -> dict:
    client = _client()
    if client is None:
        return {"available": False}
    try:
        settings = (client.table("rog_budget_settings").select("*").eq("id", True).single().execute().data or {})
        quotas = client.table("rog_profile_quotas").select("*").order("profile").execute().data or []
        since = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        rows = client.table("rog_media_usage").select("profile,media_type,status,estimated_cost_usd").gte("created_at", since).execute().data or []
        spent = sum(float(row.get("estimated_cost_usd") or 0) for row in rows if row.get("status") in {"reserved", "completed"})
        return {"available": True, "settings": settings, "quotas": quotas, "usage": rows, "reserved_usd": round(spent, 4), "remaining_usd": round(max(0, float(settings.get("monthly_limit_usd", 10)) - spent), 4)}
    except Exception:
        return {"available": False}


def media_gallery(*, user_id: str, profile: str, limit: int = 24) -> list[dict]:
    client = _client()
    if client is None or not user_id:
        return []
    try:
        response = client.table("rog_media_usage").select("id,media_type,model,estimated_cost_usd,storage_path,created_at").eq("user_id", user_id).eq("profile", profile.casefold()).eq("status", "completed").order("created_at", desc=True).limit(max(1, min(60, limit))).execute()
        items = []
        for row in (getattr(response, "data", None) or []):
            path = str(row.get("storage_path") or "")
            if not path:
                continue
            signed = client.storage.from_("rog-media").create_signed_url(path, 900)
            row["url"] = (signed or {}).get("signedURL") or (signed or {}).get("signedUrl") or ""
            items.append(row)
        return items
    except Exception:
        return []


def admin_update_budget(access_token: str, *, enabled: bool, daily_limit_usd: float, image_limit_usd: float, video_limit_usd: float) -> bool:
    from core.supabase_auth import validate_access_token
    admin = validate_access_token(access_token)
    client = _client()
    if admin is None or not admin.is_admin or client is None:
        return False
    daily = min(10.0, max(0.0, float(daily_limit_usd)))
    image = min(10.0, max(0.0, float(image_limit_usd)))
    video = min(10.0, max(0.0, float(video_limit_usd)))
    if image + video > 10.0:
        return False
    try:
        response = client.table("rog_budget_settings").update({"paid_media_enabled": bool(enabled), "daily_limit_usd": daily, "image_limit_usd": image, "video_limit_usd": video, "monthly_limit_usd": 10.0, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("id", True).execute()
        return bool(getattr(response, "data", None))
    except Exception:
        return False


def admin_update_quota(access_token: str, *, profile: str, monthly_limit_usd: float, image_enabled: bool, video_enabled: bool) -> bool:
    from core.supabase_auth import validate_access_token
    admin = validate_access_token(access_token)
    client = _client()
    if admin is None or not admin.is_admin or client is None or profile.casefold() not in {"allan", "beatriz", "tainan"}:
        return False
    try:
        response = client.table("rog_profile_quotas").update({"monthly_limit_usd": min(10.0, max(0.0, float(monthly_limit_usd))), "image_enabled": bool(image_enabled), "video_enabled": bool(video_enabled), "updated_at": datetime.now(timezone.utc).isoformat()}).eq("profile", profile.casefold()).execute()
        return bool(getattr(response, "data", None))
    except Exception:
        return False
