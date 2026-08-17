import threading
import time

from core.response_jobs import cancel_response_job, consume_response_job, drain_response_tokens, response_job_status, start_response_job


def test_response_job_is_owner_scoped_and_consumable():
    release = threading.Event()
    job_id = start_response_job(profile="Allan", agent_id="tech", target=lambda: (release.wait(1), {"answer": "ok"})[1], kwargs={})
    assert response_job_status(job_id=job_id, profile="Beatriz", agent_id="tech")["state"] == "missing"
    release.set()
    for _ in range(100):
        status = response_job_status(job_id=job_id, profile="Allan", agent_id="tech")
        if status["state"] == "done":
            break
        time.sleep(0.01)
    assert consume_response_job(job_id=job_id, profile="Allan", agent_id="tech")["result"]["answer"] == "ok"
    assert response_job_status(job_id=job_id, profile="Allan", agent_id="tech")["state"] == "missing"


def test_response_job_cancel_is_owner_scoped():
    release = threading.Event()
    job_id = start_response_job(profile="Allan", agent_id="finance", target=lambda: release.wait(1), kwargs={})
    assert not cancel_response_job(job_id=job_id, profile="Beatriz", agent_id="finance")
    assert cancel_response_job(job_id=job_id, profile="Allan", agent_id="finance")
    assert consume_response_job(job_id=job_id, profile="Allan", agent_id="finance")["state"] == "cancelled"
    release.set()


def test_stream_tokens_are_drained_only_by_owner():
    def target(on_token):
        on_token("parte 1")
        on_token(" + parte 2")
        return {"answer": "parte 1 + parte 2"}

    job_id = start_response_job(profile="Allan", agent_id="tech", target=target, kwargs={}, streaming=True)
    for _ in range(100):
        if response_job_status(job_id=job_id, profile="Allan", agent_id="tech")["state"] == "done":
            break
        time.sleep(0.01)
    assert drain_response_tokens(job_id=job_id, profile="Beatriz", agent_id="tech") == ""
    assert drain_response_tokens(job_id=job_id, profile="Allan", agent_id="tech") == "parte 1 + parte 2"
    consume_response_job(job_id=job_id, profile="Allan", agent_id="tech")
