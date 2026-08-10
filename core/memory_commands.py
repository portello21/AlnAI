from __future__ import annotations

import re
from typing import Optional

from core.memory_engine import MemoryEngine
from core.memory_consolidator import MemoryConsolidator


REMEMBER_PATTERNS = (
    r"^\s*lembre(?:-se)?\s+(?:que\s+)?",
    r"^\s*guarde\s+(?:isso\s*:?\s*)?",
    r"^\s*salve\s+(?:na\s+memoria\s+)?",
    r"^\s*memorize\s+(?:que\s+)?",
)

FORGET_PATTERNS = (
    r"^\s*esqueca\s+(?:que\s+)?",
    r"^\s*esqueça\s+(?:que\s+)?",
    r"^\s*apague\s+(?:da\s+memoria\s+)?",
    r"^\s*remova\s+(?:da\s+memoria\s+)?",
)


def _strip_patterns(
    text: str,
    patterns: tuple[str, ...],
) -> str:

    result = text

    for pattern in patterns:
        result = re.sub(
            pattern,
            "",
            result,
            flags=re.IGNORECASE,
        )

    return result.strip()


def detect_memory_command(
    user_text: str,
) -> dict:

    text = (user_text or "").strip()

    if not text:
        return {
            "command": None,
            "content": "",
        }

    for pattern in REMEMBER_PATTERNS:
        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):
            return {
                "command": "REMEMBER",
                "content": _strip_patterns(
                    text,
                    REMEMBER_PATTERNS,
                ),
            }

    for pattern in FORGET_PATTERNS:
        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):
            return {
                "command": "FORGET",
                "content": _strip_patterns(
                    text,
                    FORGET_PATTERNS,
                ),
            }

    return {
        "command": None,
        "content": text,
    }


class MemoryCommandProcessor:

    def __init__(
        self,
        engine: Optional[MemoryEngine] = None,
    ):

        self.engine = engine or MemoryEngine()
        self.consolidator = MemoryConsolidator(
            self.engine
        )


    def remember_explicit(
        self,
        profile: str,
        content: str,
    ) -> dict:

        content = (content or "").strip()

        if not content:
            return {
                "handled": True,
                "success": False,
                "command": "REMEMBER",
                "error": "empty_content",
            }

        result = self.consolidator.process_text(
            profile=profile,
            user_text=content,
            source="explicit_user_command",
        )

        return {
            "handled": True,
            "success": result.get(
                "success",
                False,
            ),
            "command": "REMEMBER",
            "result": result,
        }


    def forget_matching(
        self,
        profile: str,
        query: str,
    ) -> dict:

        query = (query or "").strip()

        if not query:
            return {
                "handled": True,
                "success": False,
                "command": "FORGET",
                "error": "empty_query",
            }

        matches = self.engine.search_memories(
            profile=profile,
            query=query,
            limit=10,
        )

        if not matches:
            return {
                "handled": True,
                "success": True,
                "command": "FORGET",
                "forgotten": 0,
                "memory_ids": [],
            }

        forgotten_ids = []

        for memory in matches:

            memory_id = memory.get("id")

            if not memory_id:
                continue

            if self.engine.forget_memory(
                memory_id
            ):
                forgotten_ids.append(
                    memory_id
                )

        return {
            "handled": True,
            "success": True,
            "command": "FORGET",
            "forgotten": len(
                forgotten_ids
            ),
            "memory_ids": forgotten_ids,
        }


    def process(
        self,
        profile: str,
        user_text: str,
    ) -> dict:

        command = detect_memory_command(
            user_text
        )

        action = command.get("command")
        content = command.get(
            "content",
            ""
        )

        if action == "REMEMBER":
            return self.remember_explicit(
                profile,
                content,
            )

        if action == "FORGET":
            return self.forget_matching(
                profile,
                content,
            )

        return {
            "handled": False,
            "success": True,
            "command": None,
        }