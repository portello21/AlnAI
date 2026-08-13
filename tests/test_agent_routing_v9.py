from core.agent_runtime import normalize_agent_id, route_query


def test_agent_aliases_are_normalized():
    assert normalize_agent_id("root") == "orchestrator"
    assert normalize_agent_id("finance_agent") == "finance"
    assert normalize_agent_id("TECH_AGENT") == "tech"


def test_empty_and_general_requests_stay_on_core():
    assert route_query("") == "orchestrator"
    assert route_query("qual a capital do canada") == "orchestrator"


def test_domain_requests_route_without_llm_cost():
    assert route_query("analise meu financiamento e os juros do banco") == "finance"
    assert route_query("corrija este bug no meu codigo python e docker") == "tech"
    assert route_query("monte um treino de academia para hipertrofia") == "coach"
    assert route_query("quero melhorar a margem e as vendas da minha empresa") == "business"
    assert route_query("corrija minha gramatica em ingles") == "english"
    assert route_query("resuma este pdf e extraia os dados") == "document"
    assert route_query("organize minha agenda e minhas tarefas") == "personal"


def test_domain_ownership_wins_common_document_ties():
    assert route_query("analise este pdf do meu financiamento e extrato bancario") == "finance"
    assert route_query("analise este arquivo com erro de python") == "tech"
