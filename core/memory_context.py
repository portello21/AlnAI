from __future__ import annotations

from typing import Optional


DEFAULT_MAX_MEMORIES = 6
DEFAULT_MAX_CHARS = 4000

HEADER = "MEMORIAS RELEVANTES DO USUARIO:"


class MemoryContextBuilder:
    """
    Converte resultados do MemoryEngine em contexto compacto
    para consumo por agentes/LLMs.

    O budget e aplicado sobre o TEXTO FINAL renderizado,
    incluindo header, numeracao e quebras de linha.
    """

    def __init__(
        self,
        max_memories: int = DEFAULT_MAX_MEMORIES,
        max_chars: int = DEFAULT_MAX_CHARS,
    ):

        self.max_memories = max(
            1,
            int(max_memories),
        )

        self.max_chars = max(
            200,
            int(max_chars),
        )


    def _limits(
        self,
        max_memories: Optional[int],
        max_chars: Optional[int],
    ) -> tuple[int, int]:

        memory_limit = (
            self.max_memories
            if max_memories is None
            else max(
                1,
                int(max_memories),
            )
        )

        char_limit = (
            self.max_chars
            if max_chars is None
            else max(
                200,
                int(max_chars),
            )
        )

        return (
            memory_limit,
            char_limit,
        )


    def build(
        self,
        memories: list[dict],
        max_memories: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> dict:

        memory_limit, char_limit = self._limits(
            max_memories,
            max_chars,
        )

        if not memories:

            return {
                "text": "",
                "memory_count": 0,
                "memory_ids": [],
                "characters": 0,
                "memories": [],
                "truncated": False,
                "budget_chars": char_limit,
            }

        selected = []
        ids = []
        seen_ids = set()

        lines = [
            HEADER
        ]

        truncated = False


        for memory in memories:

            if len(selected) >= memory_limit:
                break

            memory_id = str(
                memory.get(
                    "id",
                    "",
                )
            ).strip()

            content = str(
                memory.get(
                    "content",
                    "",
                )
            ).strip()

            if not content:
                continue

            if memory_id:

                if memory_id in seen_ids:
                    continue

                seen_ids.add(
                    memory_id
                )


            item_number = (
                len(selected) + 1
            )

            prefix = (
                f"{item_number}. "
            )

            candidate_line = (
                prefix + content
            )

            candidate_text = "\n".join(
                lines
                + [candidate_line]
            )


            # ------------------------------------------------
            # Cabe inteiro no budget.
            # ------------------------------------------------

            if len(candidate_text) <= char_limit:

                selected.append(
                    dict(memory)
                )

                lines.append(
                    candidate_line
                )

                if memory_id:
                    ids.append(
                        memory_id
                    )

                continue


            # ------------------------------------------------
            # Se nenhuma memoria entrou ainda,
            # truncamos a primeira para usar o budget restante.
            # ------------------------------------------------

            if not selected:

                base_text = "\n".join(
                    [
                        HEADER,
                        prefix,
                    ]
                )

                available = (
                    char_limit
                    - len(base_text)
                )

                if available <= 0:
                    break

                if available <= 3:
                    clipped = (
                        content[:available]
                    )
                else:
                    clipped = (
                        content[
                            : available - 3
                        ]
                        + "..."
                    )

                copy = dict(
                    memory
                )

                copy[
                    "content"
                ] = clipped

                selected.append(
                    copy
                )

                lines.append(
                    prefix + clipped
                )

                if memory_id:
                    ids.append(
                        memory_id
                    )

                truncated = True

            break


        if not selected:

            return {
                "text": "",
                "memory_count": 0,
                "memory_ids": [],
                "characters": 0,
                "memories": [],
                "truncated": False,
                "budget_chars": char_limit,
            }


        text = "\n".join(
            lines
        )

        # Defesa final.
        if len(text) > char_limit:

            text = text[
                :char_limit
            ]

            truncated = True


        return {
            "text": text,
            "memory_count": len(
                selected
            ),
            "memory_ids": ids,
            "characters": len(
                text
            ),
            "memories": selected,
            "truncated": truncated,
            "budget_chars": char_limit,
        }


    def select(
        self,
        memories: list[dict],
        max_memories: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> list[dict]:
        """
        Mantem compatibilidade com codigo futuro/legado.
        """

        return self.build(
            memories=memories,
            max_memories=max_memories,
            max_chars=max_chars,
        )["memories"]
