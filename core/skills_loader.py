from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = BASE_DIR / "skills"


AGENT_SKILLS = {
    "orchestrator": [],
    "personal": [],
    "finance": ["financial_cad_planner"],
    "tech": [],
    "coach": [],
    "business": [],
    "english": [],
    "document": [],
}


def list_available_skills() -> list[str]:
    if not SKILLS_DIR.exists():
        return []

    return sorted(
        d.name
        for d in SKILLS_DIR.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    )


def load_skill(skill_name: str) -> str:
    skill_path = SKILLS_DIR / skill_name / "SKILL.md"

    if not skill_path.exists():
        return ""

    return skill_path.read_text(encoding="utf-8")


def get_agent_skills(agent_id: str) -> list[str]:
    return AGENT_SKILLS.get(agent_id, [])


def build_agent_skills_context(agent_id: str) -> str:
    names = get_agent_skills(agent_id)

    if not names:
        return ""

    blocks = []

    for name in names:
        content = load_skill(name)

        if content.strip():
            blocks.append(
                f"### SKILL: {name}\n{content.strip()}"
            )

    if not blocks:
        return ""

    return (
        "\n\n"
        "SKILLS ESPECIFICAS DISPONIVEIS PARA ESTE AGENTE:\n\n"
        + "\n\n".join(blocks)
    )


def find_skill_for_agent(
    agent_id: str,
    skill_name: str
) -> Optional[str]:

    if skill_name not in get_agent_skills(agent_id):
        return None

    content = load_skill(skill_name)

    return content if content.strip() else None