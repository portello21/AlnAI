import json
from pathlib import Path

from core.agent_runtime import AGENTS, ROUTE_TERMS, route_query
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


def test_every_routing_term_has_a_deterministic_eval_case():
    evaluated = 0
    for agent, terms in ROUTE_TERMS.items():
        for term in terms:
            assert route_query(f"Preciso de ajuda com {term}.") == agent
            evaluated += 1
    assert evaluated >= 100


def test_family_namespace_matrix_has_no_cross_profile_access():
    profiles = ("allan", "beatriz", "natan", "tainan")
    agents = tuple(AGENTS)
    evaluated = 0
    for profile in profiles:
        for agent in agents:
            for owner in profiles:
                allowed = validate_ownership(profile, agent, f"profile:{owner}")
                assert allowed is (profile == owner)
                evaluated += 1
            shared = validate_ownership(profile, agent, "shared:allan_beatriz:finance")
            assert shared is (profile in {"allan", "beatriz"} and agent == "finance")
            evaluated += 1
    assert evaluated >= 150
