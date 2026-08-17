from __future__ import annotations

import hashlib
import hmac
import logging
import threading

import httpx

from core.config import Config

LOGGER = logging.getLogger("rog.observability")
ALLOWED_PROPERTIES = {"agent", "provider", "model", "success", "duration_ms", "error_type", "fallback", "status", "auth_backend"}


def _safe_properties(properties: dict | None) -> dict:
    source = properties if isinstance(properties, dict) else {}
    return {key: source[key] for key in ALLOWED_PROPERTIES if key in source and isinstance(source[key], (str, int, float, bool, type(None)))}


def _anonymous_id(user_id: str) -> str:
    value = str(user_id or "")
    secret = Config.OBSERVABILITY_HASH_SECRET
    if not value or len(secret) < 16:
        return "anonymous"
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def init_error_monitoring() -> bool:
    if not Config.SENTRY_DSN:
        return False
    try:
        import sentry_sdk

        def scrub(event, hint):
            event.pop("request", None)
            event.pop("user", None)
            event.pop("breadcrumbs", None)
            return event

        sentry_sdk.init(dsn=Config.SENTRY_DSN, send_default_pii=False, traces_sample_rate=0.0, before_send=scrub)
        return True
    except Exception as exc:
        LOGGER.warning("Sentry initialization failed: %s", type(exc).__name__)
        return False


def capture_exception(exc: Exception, *, component: str) -> None:
    LOGGER.exception("%s failed: %s", component, type(exc).__name__)
    if not Config.SENTRY_DSN:
        return
    try:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("component", str(component or "unknown")[:80])
            sentry_sdk.capture_exception(exc)
    except Exception:
        return


def capture_product_event(event: str, *, user_id: str = "", properties: dict | None = None) -> None:
    if not Config.POSTHOG_API_KEY or not str(event or "").strip():
        return
    payload = {
        "api_key": Config.POSTHOG_API_KEY,
        "event": str(event)[:80],
        "properties": {"distinct_id": _anonymous_id(user_id), **_safe_properties(properties)},
    }

    def send() -> None:
        try:
            httpx.post(Config.POSTHOG_HOST.rstrip("/") + "/capture/", json=payload, timeout=2.0)
        except Exception:
            return

    threading.Thread(target=send, daemon=True).start()
