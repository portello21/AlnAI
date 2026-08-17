import json
from pathlib import Path

from core.agent_runtime import AGENTS
from core.vector_rag_v9 import validate_ownership


CASES = json.loads((Path(__file__).resolve().parents[1] / "evals" / "quality_cases.json").read_text(encoding="utf-8"))


def test_quality_eval_dataset_has_unique_runnable_cases():
    assert len(CASES) >= 5
    assert len({case["id"] for case in CASES}) == len(CASES)
    assert all(case["agent"] in AGENTS for case in CASES)


def test_isolation_eval_cases_fail_closed():
    isolation_cases = [case for case in CASES if "forbidden_namespace" in case]
    assert isolation_cases
    for case in isolation_cases:
        assert not validate_ownership(case["profile"], case["agent"], case["forbidden_namespace"])
