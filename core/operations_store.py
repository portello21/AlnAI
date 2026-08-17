from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from core.config import Config
from core.supabase_optional import create_privileged_client
import httpx

LOGGER = logging.getLogger("rog.operations")


def _client():
    return create_privileged_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)


def record_usage(*, user_id: str, profile: str, request_id: str, agent_id: str, result: dict) -> bool:
    client = _client()
    if client is None or not user_id or not request_id:
        return False
    record = {"user_id": user_id, "profile": str(profile or "").casefold(), "request_id": request_id, "agent_id": agent_id, "provider": result.get("provider"), "model": result.get("model"), "success": bool(result.get("success", False)), "duration_ms": result.get("duration_ms"), "input_tokens": result.get("input_tokens"), "output_tokens": result.get("output_tokens"), "estimated_cost": result.get("estimated_cost"), "error_type": result.get("error_type") or None}
    try:
        client.table("rog_api_usage").upsert(record, on_conflict="request_id").execute()
        return True
    except Exception as exc:
        LOGGER.warning("usage record failed: %s", type(exc).__name__)
        return False


def record_usage_async(**kwargs) -> None:
    threading.Thread(target=record_usage, kwargs=kwargs, daemon=True).start()


def record_audit(*, event_type: str, outcome: str, user_id: str = "", profile: str = "", metadata: dict | None = None) -> bool:
    client = _client()
    if client is None or outcome not in {"success", "failure", "denied"}:
        return False
    safe_keys = {"agent_id", "provider", "error_type", "auth_backend", "reason"}
    safe_metadata = {key: value for key, value in (metadata or {}).items() if key in safe_keys and isinstance(value, (str, int, float, bool, type(None)))}
    try:
        client.table("rog_audit_events").insert({"user_id": user_id or None, "profile": str(profile or "").casefold() or None, "event_type": str(event_type or "unknown")[:80], "outcome": outcome, "metadata": safe_metadata}).execute()
        return True
    except Exception as exc:
        LOGGER.warning("audit record failed: %s", type(exc).__name__)
        return False


def record_audit_async(**kwargs) -> None:
    threading.Thread(target=record_audit, kwargs=kwargs, daemon=True).start()


def enforce_retention() -> dict:
    client = _client()
    if client is None:
        return {"success": False}
    now = datetime.now(timezone.utc)
    audit_before = (now - timedelta(days=Config.AUDIT_RETENTION_DAYS)).isoformat()
    usage_before = (now - timedelta(days=Config.USAGE_RETENTION_DAYS)).isoformat()
    try:
        client.table("rog_audit_events").delete().lt("created_at", audit_before).execute()
        client.table("rog_api_usage").delete().lt("created_at", usage_before).execute()
        return {"success": True, "audit_before": audit_before, "usage_before": usage_before}
    except Exception as exc:
        LOGGER.warning("retention cleanup failed: %s", type(exc).__name__)
        return {"success": False}


def operations_summary(*, days: int = 7) -> dict:
    client = _client()
    if client is None:
        return {"available": False}
    since = (datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))).isoformat()
    try:
        usage_response = client.table("rog_api_usage").select("provider,success,duration_ms,estimated_cost").gte("created_at", since).limit(1000).execute()
        audit_response = client.table("rog_audit_events").select("outcome").gte("created_at", since).limit(1000).execute()
        profiles_response = client.table("rog_user_profiles").select("active").limit(100).execute()
        usage = [row for row in (getattr(usage_response, "data", None) or []) if isinstance(row, dict)]
        audits = [row for row in (getattr(audit_response, "data", None) or []) if isinstance(row, dict)]
        profiles = [row for row in (getattr(profiles_response, "data", None) or []) if isinstance(row, dict)]
        durations = [int(row["duration_ms"]) for row in usage if isinstance(row.get("duration_ms"), (int, float))]
        costs = [float(row["estimated_cost"]) for row in usage if isinstance(row.get("estimated_cost"), (int, float, str))]
        providers: dict[str, int] = {}
        for row in usage:
            provider = str(row.get("provider") or "unknown")
            providers[provider] = providers.get(provider, 0) + 1
        return {"available": True, "requests": len(usage), "successes": sum(1 for row in usage if row.get("success") is True), "average_duration_ms": round(sum(durations) / len(durations)) if durations else None, "estimated_cost": round(sum(costs), 6) if costs else None, "denied_or_failed_events": sum(1 for row in audits if row.get("outcome") in {"denied", "failure"}), "active_users": sum(1 for row in profiles if row.get("active") is True), "providers": providers, "window_days": max(1, int(days))}
    except Exception as exc:
        LOGGER.warning("operations summary failed: %s", type(exc).__name__)
        return {"available": False}


def list_user_profiles() -> list[dict]:
    client = _client()
    if client is None:
        return []
    try:
        response = client.table("rog_user_profiles").select("user_id,profile,role,active,created_at,updated_at").order("profile").execute()
        return [row for row in (getattr(response, "data", None) or []) if isinstance(row, dict)]
    except Exception:
        return []


def set_user_active(*, user_id: str, active: bool) -> bool:
    client = _client()
    if client is None or not user_id:
        return False


def admin_list_profiles(access_token: str) -> list[dict]:
    """List family profiles through the signed-in admin JWT and RLS."""
    if not access_token or not Config.SUPABASE_URL or not Config.SUPABASE_PUBLISHABLE_KEY:
        return []
    try:
        response = httpx.get(
            f"{Config.SUPABASE_URL.rstrip('/')}/rest/v1/rog_user_profiles",
            headers={"apikey": Config.SUPABASE_PUBLISHABLE_KEY, "Authorization": f"Bearer {access_token}"},
            params={"select": "user_id,profile,role,active,updated_at,password_change_required", "order": "profile.asc"},
            timeout=5.0,
        )
        response.raise_for_status()
        rows = response.json()
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    except Exception:
        return []


def admin_set_profile_active(access_token: str, *, user_id: str, active: bool) -> bool:
    """Activate or suspend a member after revalidating the server-side admin."""
    if not access_token or not user_id:
        return False
    try:
        from core.supabase_auth import validate_access_token
        admin = validate_access_token(access_token)
        client = _client()
        if admin is None or not admin.is_admin or client is None or admin.user_id == user_id:
            return False
        response = client.table("rog_user_profiles").update({"active": bool(active), "updated_at": datetime.now(timezone.utc).isoformat()}).eq("user_id", user_id).execute()
        return len(getattr(response, "data", None) or []) == 1
    except Exception:
        return False
    try:
        response = client.table("rog_user_profiles").update({"active": bool(active), "updated_at": datetime.now(timezone.utc).isoformat()}).eq("user_id", user_id).execute()
        return bool(getattr(response, "data", None) or [])
    except Exception:
        return False
