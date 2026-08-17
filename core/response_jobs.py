from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable


@dataclass
class _Job:
    profile: str
    agent_id: str
    future: Future
    cancelled: threading.Event
    tokens: deque[str]
    created_at: float


_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="rog-response")
_LOCK = threading.RLock()
_JOBS: dict[str, _Job] = {}


def start_response_job(*, profile: str, agent_id: str, target: Callable, kwargs: dict, streaming: bool = False) -> str:
    owner = str(profile or "").strip().casefold()
    agent = str(agent_id or "").strip().casefold()
    if not owner or not agent:
        raise ValueError("job owner is required")
    cancelled = threading.Event()
    tokens: deque[str] = deque()

    def on_token(value: str) -> None:
        if not cancelled.is_set() and value:
            tokens.append(str(value))

    def run():
        if cancelled.is_set():
            return None
        call_kwargs = dict(kwargs)
        if streaming:
            call_kwargs["on_token"] = on_token
        result = target(**call_kwargs)
        return None if cancelled.is_set() else result

    job_id = uuid.uuid4().hex
    future = _EXECUTOR.submit(run)
    with _LOCK:
        _JOBS[job_id] = _Job(owner, agent, future, cancelled, tokens, time.monotonic())
    return job_id


def response_job_status(*, job_id: str, profile: str, agent_id: str) -> dict:
    with _LOCK:
        job = _JOBS.get(str(job_id or ""))
    if job is None or job.profile != str(profile or "").strip().casefold() or job.agent_id != str(agent_id or "").strip().casefold():
        return {"state": "missing"}
    if job.cancelled.is_set():
        return {"state": "cancelled"}
    if not job.future.done():
        return {"state": "running"}
    try:
        return {"state": "done", "result": job.future.result()}
    except Exception as exc:
        return {"state": "failed", "error_type": type(exc).__name__}


def cancel_response_job(*, job_id: str, profile: str, agent_id: str) -> bool:
    with _LOCK:
        job = _JOBS.get(str(job_id or ""))
    if job is None or job.profile != str(profile or "").strip().casefold() or job.agent_id != str(agent_id or "").strip().casefold():
        return False
    job.cancelled.set()
    job.future.cancel()
    return True


def drain_response_tokens(*, job_id: str, profile: str, agent_id: str) -> str:
    with _LOCK:
        job = _JOBS.get(str(job_id or ""))
        if job is None or job.profile != str(profile or "").strip().casefold() or job.agent_id != str(agent_id or "").strip().casefold():
            return ""
        output = "".join(job.tokens)
        job.tokens.clear()
    return output


def consume_response_job(*, job_id: str, profile: str, agent_id: str) -> dict:
    status = response_job_status(job_id=job_id, profile=profile, agent_id=agent_id)
    if status["state"] in {"done", "failed", "cancelled"}:
        with _LOCK:
            _JOBS.pop(str(job_id or ""), None)
    return status
