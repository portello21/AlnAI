from __future__ import annotations

import threading
import time
from collections import Counter, deque

_LOCK = threading.RLock()
_EVENTS: deque[dict] = deque(maxlen=500)


def record_runtime_event(*, provider: str, success: bool, duration_ms: int, error_type: str = "", fallback: bool = False) -> None:
    """Record operational metadata only; prompts, answers and identities are forbidden."""
    event = {
        "provider": str(provider or "none")[:40],
        "success": bool(success),
        "duration_ms": max(0, int(duration_ms)),
        "error_type": str(error_type or "")[:60],
        "fallback": bool(fallback),
        "timestamp": int(time.time()),
    }
    with _LOCK:
        _EVENTS.append(event)


def runtime_snapshot() -> dict:
    with _LOCK:
        events = list(_EVENTS)
    durations = [event["duration_ms"] for event in events]
    successes = sum(1 for event in events if event["success"])
    return {
        "requests": len(events),
        "successes": successes,
        "failures": len(events) - successes,
        "fallbacks": sum(1 for event in events if event["fallback"]),
        "average_duration_ms": round(sum(durations) / len(durations)) if durations else None,
        "providers": dict(Counter(event["provider"] for event in events)),
        "errors": dict(Counter(event["error_type"] for event in events if event["error_type"])),
    }


def clear_runtime_events() -> None:
    with _LOCK:
        _EVENTS.clear()
