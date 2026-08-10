from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)

import re
from typing import Any


@dataclass(frozen=True)
class SourceReference:

    source_id: str
    evidence_id: str
    title: str
    url: str
    domain: str
    snippet: str
    quality_score: float
    authority_score: float
    relevance_score: float

    def to_dict(self) -> dict[str, Any]:

        return asdict(self)


@dataclass(frozen=True)
class CitationValidationResult:

    sources: tuple[SourceReference, ...]
    cited_source_ids: tuple[str, ...]
    invalid_citations: tuple[str, ...]
    grounded: bool

    @property
    def cited_sources(
        self,
    ) -> tuple[SourceReference, ...]:

        cited = set(
            self.cited_source_ids
        )

        return tuple(
            source
            for source in self.sources
            if source.source_id in cited
        )

    def to_dict(self) -> dict[str, Any]:

        return {
            "sources": [
                source.to_dict()
                for source in self.sources
            ],
            "cited_source_ids":
                list(
                    self.cited_source_ids
                ),
            "cited_sources": [
                source.to_dict()
                for source in self.cited_sources
            ],
            "invalid_citations":
                list(
                    self.invalid_citations
                ),
            "grounded":
                self.grounded,
        }


class SourceGroundingEngine:

    CITATION_PATTERN = re.compile(
        r"\[(S\d+)\]",
        re.IGNORECASE,
    )


    def _source_rank_score(
        self,
        item: Any,
    ) -> float:

        authority = float(
            getattr(
                item,
                "authority_score",
                0.0,
            )
            or 0.0
        )

        quality = float(
            getattr(
                item,
                "quality_score",
                0.0,
            )
            or 0.0
        )

        relevance = float(
            getattr(
                item,
                "relevance_score",
                0.0,
            )
            or 0.0
        )

        domain = str(
            getattr(
                item,
                "domain",
                "",
            )
            or ""
        ).lower()


        # Fontes de autoridade maxima recebem
        # prioridade extra.

        top_authority_bonus = (
            0.20
            if authority >= 0.95
            else 0.0
        )


        strong_authority_bonus = (
            0.05
            if authority >= 0.80
            else 0.0
        )


        low_authority_penalty = (
            0.15
            if authority <= 0.30
            else 0.0
        )


        social_penalty = (
            0.20
            if any(
                token in domain
                for token in (
                    "telegram",
                    "t.me",
                    "reddit",
                    "facebook",
                    "instagram",
                    "tiktok",
                    "youtube",
                )
            )
            else 0.0
        )


        score = (
            authority * 0.45
            + quality * 0.35
            + relevance * 0.20
            + top_authority_bonus
            + strong_authority_bonus
            - low_authority_penalty
            - social_penalty
        )


        return round(
            score,
            6,
        )


    def _source_tier(
        self,
        item: Any,
    ) -> str:

        authority = float(
            getattr(
                item,
                "authority_score",
                0.0,
            )
            or 0.0
        )

        quality = float(
            getattr(
                item,
                "quality_score",
                0.0,
            )
            or 0.0
        )


        if authority >= 0.95:
            return "top_authority"

        if authority >= 0.80:
            return "high_authority"

        if quality >= 0.70:
            return "strong_secondary"

        if quality >= 0.50:
            return "secondary"

        return "low"


    def build_sources(
        self,
        evidence_set: Any,
    ) -> tuple[SourceReference, ...]:

        if evidence_set is None:
            return tuple()


        usable_items = [
            item
            for item in evidence_set.items
            if not getattr(
                item,
                "blocked",
                False,
            )
            and not getattr(
                item,
                "duplicate",
                False,
            )
            and str(
                getattr(
                    item,
                    "url",
                    "",
                )
                or ""
            ).strip()
        ]


        # ====================================================
        # SOURCE RANKING V2
        #
        # S1 deve representar a melhor fonte disponivel,
        # nao simplesmente o primeiro resultado da busca.
        # ====================================================

        usable_items.sort(
            key=lambda item: (
                -self._source_rank_score(
                    item
                ),

                -float(
                    getattr(
                        item,
                        "authority_score",
                        0.0,
                    )
                    or 0.0
                ),

                -float(
                    getattr(
                        item,
                        "quality_score",
                        0.0,
                    )
                    or 0.0
                ),

                -float(
                    getattr(
                        item,
                        "relevance_score",
                        0.0,
                    )
                    or 0.0
                ),

                int(
                    getattr(
                        item,
                        "rank",
                        999999,
                    )
                    or 999999
                ),
            )
        )


        sources: list[
            SourceReference
        ] = []


        for index, item in enumerate(
            usable_items,
            start=1,
        ):

            sources.append(
                SourceReference(

                    source_id=
                        f"S{index}",

                    evidence_id=
                        str(
                            item.evidence_id
                        ),

                    title=
                        str(
                            item.title
                            or ""
                        ),

                    url=
                        str(
                            item.url
                            or ""
                        ),

                    domain=
                        str(
                            item.domain
                            or ""
                        ),

                    snippet=
                        str(
                            item.snippet
                            or ""
                        ),

                    quality_score=
                        float(
                            item.quality_score
                        ),

                    authority_score=
                        float(
                            item.authority_score
                        ),

                    relevance_score=
                        float(
                            item.relevance_score
                        ),
                )
            )


        return tuple(
            sources
        )


    def source_catalog(
        self,
        evidence_set: Any,
    ) -> str:

        sources = self.build_sources(
            evidence_set
        )


        if not sources:

            return ""


        lines = [
            "FONTES AUTORIZADAS PARA CITACAO:",
            (
                "Use SOMENTE os IDs abaixo "
                "para sustentar afirmacoes factuais."
            ),
            (
                "Formato obrigatório da citacao: "
                "[S1], [S2], [S3]..."
            ),
            (
                "Nao invente IDs. "
                "Nao transforme URLs nao listadas "
                "em fontes."
            ),
            "",
        ]


        for source in sources:

            snippet = (
                source.snippet
                .replace(
                    "\n",
                    " ",
                )
                .strip()
            )

            if len(snippet) > 600:

                snippet = (
                    snippet[:600]
                    + "..."
                )


            lines.extend(
                [
                    (
                        f"[{source.source_id}] "
                        f"{source.title}"
                    ),
                    (
                        f"URL: "
                        f"{source.url}"
                    ),
                    (
                        f"DOMAIN: "
                        f"{source.domain}"
                    ),
                    (
                        f"EVIDENCE_ID: "
                        f"{source.evidence_id}"
                    ),
                    (
                        f"QUALITY: "
                        f"{source.quality_score:.4f}"
                    ),
                    (
                        f"SNIPPET: "
                        f"{snippet}"
                    ),
                    "",
                ]
            )


        return "\n".join(
            lines
        ).strip()


    def validate(
        self,
        answer: str,
        evidence_set: Any,
    ) -> CitationValidationResult:

        sources = self.build_sources(
            evidence_set
        )

        valid_ids = {
            source.source_id
            for source in sources
        }


        found = [
            match.upper()
            for match in
            self.CITATION_PATTERN.findall(
                str(
                    answer
                    or ""
                )
            )
        ]


        cited_ids = tuple(
            dict.fromkeys(
                found
            )
        )


        invalid = tuple(
            source_id
            for source_id in cited_ids
            if source_id not in valid_ids
        )


        valid_cited = tuple(
            source_id
            for source_id in cited_ids
            if source_id in valid_ids
        )


        grounded = bool(
            sources
            and valid_cited
            and not invalid
        )


        return CitationValidationResult(
            sources=sources,
            cited_source_ids=
                valid_cited,
            invalid_citations=
                invalid,
            grounded=
                grounded,
        )
