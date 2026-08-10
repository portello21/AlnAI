from dataclasses import dataclass


PRIVATE_PROFILES = {
    "allan",
    "beatriz",
    "natan",
    "tainan",
}


COUPLE_PROFILES = {
    "allan",
    "beatriz",
}


def normalize_profile(profile: str | None) -> str:
    return str(
        profile
        or ""
    ).strip().lower()


def normalize_agent(agent_id: str | None) -> str:
    return str(
        agent_id
        or ""
    ).strip().lower()


def private_namespace(
    profile: str,
) -> str:

    profile = normalize_profile(
        profile
    )

    if profile not in PRIVATE_PROFILES:
        raise ValueError(
            f"Perfil nao autorizado: {profile}"
        )

    return f"profile:{profile}"


def couple_finance_namespace() -> str:
    return "shared:allan_beatriz:finance"


def allowed_namespaces(
    profile: str,
    agent_id: str,
) -> tuple[str, ...]:

    profile = normalize_profile(
        profile
    )

    agent_id = normalize_agent(
        agent_id
    )


    if profile not in PRIVATE_PROFILES:

        return ()


    allowed = [
        private_namespace(
            profile
        )
    ]


    # Allan e Beatriz compartilham SOMENTE financeiro.
    if (
        profile in COUPLE_PROFILES
        and agent_id == "finance"
    ):

        allowed.append(
            couple_finance_namespace()
        )


    return tuple(
        allowed
    )


def write_namespace(
    profile: str,
    agent_id: str,
    *,
    shared_finance: bool = False,
) -> str:

    profile = normalize_profile(
        profile
    )

    agent_id = normalize_agent(
        agent_id
    )


    if (
        shared_finance
        and profile in COUPLE_PROFILES
        and agent_id == "finance"
    ):

        return couple_finance_namespace()


    return private_namespace(
        profile
    )


def can_access_namespace(
    profile: str,
    agent_id: str,
    namespace: str,
) -> bool:

    return (
        namespace
        in allowed_namespaces(
            profile,
            agent_id,
        )
    )


def profile_session_key(
    profile: str,
    suffix: str,
) -> str:

    return (
        f"profile::{normalize_profile(profile)}::{suffix}"
    )
