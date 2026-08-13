from __future__ import annotations

from dataclasses import dataclass

from core.memory_commands import MemoryCommandProcessor, detect_memory_command
from core.memory_context import MemoryContextBuilder
from core.memory_engine import MemoryEngine
from core.profile_access import COUPLE_PROFILES, normalize_agent, normalize_profile

SHARED_FINANCE_MEMORY_PROFILE = "shared:allan_beatriz:finance"


@dataclass(frozen=True)
class MemoryCommandResult:
    handled: bool
    message: str = ""
    success: bool = True


class FamilyMemoryService:
    """Security boundary around MemoryEngine for family profiles.

    Private memories keep using the real profile identity for backward
    compatibility. Shared memory is a distinct pseudo-profile and is only ever
    reachable from Finance Agent for Allan or Beatriz.
    """

    def __init__(self, engine: MemoryEngine | None = None):
        self.engine = engine or MemoryEngine()
        self.commands = MemoryCommandProcessor(self.engine)
        self.context_builder = MemoryContextBuilder(max_memories=5, max_chars=3000)

    @staticmethod
    def _is_shared_allowed(profile: str, agent_id: str) -> bool:
        return (
            normalize_profile(profile) in COUPLE_PROFILES
            and normalize_agent(agent_id) == "finance"
        )

    def command_profile(self, profile: str, agent_id: str, *, shared_finance: bool) -> str:
        if shared_finance and self._is_shared_allowed(profile, agent_id):
            return SHARED_FINANCE_MEMORY_PROFILE
        return str(profile or "").strip()

    def process_explicit_command(
        self,
        profile: str,
        agent_id: str,
        text: str,
        *,
        shared_finance: bool = False,
    ) -> MemoryCommandResult:
        detected = detect_memory_command(text)
        if not detected.get("command"):
            return MemoryCommandResult(handled=False)

        target = self.command_profile(
            profile,
            agent_id,
            shared_finance=shared_finance,
        )
        result = self.commands.process(profile=target, user_text=text)
        action = result.get("command")

        if action == "REMEMBER":
            if result.get("success"):
                scope = "financeira compartilhada" if target == SHARED_FINANCE_MEMORY_PROFILE else "privada"
                return MemoryCommandResult(True, f"Memória {scope} salva.", True)
            return MemoryCommandResult(True, "Não consegui salvar essa memória.", False)

        if action == "FORGET":
            count = int(result.get("forgotten", 0) or 0)
            if count:
                return MemoryCommandResult(True, f"Removi {count} memória(s) deste espaço.", True)
            return MemoryCommandResult(True, "Não encontrei memória correspondente neste espaço.", True)

        return MemoryCommandResult(True, "Comando de memória processado.", bool(result.get("success", True)))

    def shared_finance_context(self, profile: str, agent_id: str, query: str) -> str:
        if not self._is_shared_allowed(profile, agent_id):
            return ""
        try:
            memories = self.engine.search_memories(
                profile=SHARED_FINANCE_MEMORY_PROFILE,
                query=query,
                limit=8,
            )
        except Exception:
            return ""
        if not memories:
            return ""
        built = self.context_builder.build(memories=memories, max_memories=5, max_chars=3000)
        text = str(built.get("text", "") or "").strip()
        if not text:
            return ""
        return "MEMÓRIAS FINANCEIRAS COMPARTILHADAS ALLAN ↔ BEATRIZ:\n" + text
