from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)

import re
from typing import Any


@dataclass(frozen=True)
class GroundedClaim:

    claim_id: str

    text: str

    citation_ids: tuple[str, ...]

    valid_citation_ids: tuple[str, ...]

    invalid_citation_ids: tuple[str, ...]

    cited: bool

    validly_cited: bool

    claim_type: str = "external_fact"

    requires_citation: bool = True

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return asdict(
            self
        )


@dataclass(frozen=True)
class ClaimGroundingResult:

    claims: tuple[
        GroundedClaim,
        ...
    ]

    claim_count: int

    cited_claim_count: int

    validly_cited_claim_count: int

    unsupported_claim_count: int

    invalid_claim_count: int

    citation_coverage: float

    valid_citation_coverage: float

    grounding_score: float

    grounded: bool

    @property
    def unsupported_claims(
        self,
    ) -> tuple[
        GroundedClaim,
        ...
    ]:

        return tuple(
            claim
            for claim in self.claims
            if not claim.validly_cited
        )


    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {

            "claims": [
                claim.to_dict()
                for claim
                in self.claims
            ],

            "claim_count":
                self.claim_count,

            "cited_claim_count":
                self.cited_claim_count,

            "validly_cited_claim_count":
                self.validly_cited_claim_count,

            "unsupported_claim_count":
                self.unsupported_claim_count,

            "invalid_claim_count":
                self.invalid_claim_count,

            "citation_coverage":
                self.citation_coverage,

            "valid_citation_coverage":
                self.valid_citation_coverage,

            "grounding_score":
                self.grounding_score,

            "grounded":
                self.grounded,

            "unsupported_claims": [
                claim.to_dict()
                for claim
                in self.unsupported_claims
            ],
        }


class ClaimGroundingEngine:

    CITATION_PATTERN = re.compile(
        r"\[(S\d+)\]",
        re.IGNORECASE,
    )


    BULLET_PATTERN = re.compile(
        r"^\s*(?:[-*•]|\d+[.)])\s+"
    )


    HEADING_PATTERN = re.compile(
        r"^\s*#{1,6}\s+"
    )


    def classify_claim_type(
        self,
        text: str,
    ) -> str:

        plain = re.sub(
            r"[*_`>#]",
            "",
            str(
                text
                or ""
            ),
        ).strip().lower()


        verification_patterns = (

            r"\bresultado da verifica[c?][a?]o\b",

            r"\bparcialmente verificado\b",

            r"\btotalmente verificado\b",

            r"\bn[a?]o verificado\b",

            r"\bconfian[c?]a de aproximadamente\b",

            r"\bconfian[c?]a da verifica[c?][a?]o\b",
        )


        recommendation_patterns = (

            r"^\s*recomenda-se\b",

            r"^\s*recomendamos\b",

            r"^\s*consulte\b",

            r"^\s*verifique\b",

            r"^\s*vale consultar\b",

            r"^\s*para uma conclus[a?]o precisa\b",
        )


        if any(
            re.search(
                pattern,
                plain,
                re.IGNORECASE,
            )
            for pattern in
            verification_patterns
        ):

            return "verification_meta"


        if any(
            re.search(
                pattern,
                plain,
                re.IGNORECASE,
            )
            for pattern in
            recommendation_patterns
        ):

            return "recommendation"


        return "external_fact"


    def _requires_citation(
        self,
        claim_type: str,
    ) -> bool:

        return (
            claim_type
            == "external_fact"
        )


    def _clean_line(
        self,
        text: str,
    ) -> str:

        text = (
            self.HEADING_PATTERN.sub(
                "",
                text,
            )
        )

        text = (
            self.BULLET_PATTERN.sub(
                "",
                text,
            )
        )

        return text.strip()


    def _is_claim_candidate(
        self,
        text: str,
    ) -> bool:

        stripped = (
            self.CITATION_PATTERN.sub(
                "",
                text,
            )
            .strip()
        )


        if not stripped:

            return False


        # Ignora labels muito curtos,
        # headings e linhas que parecem apenas links.

        if len(
            stripped
        ) < 20:

            return False


        if (
            stripped.startswith(
                "http://"
            )
            or stripped.startswith(
                "https://"
            )
        ):

            return False


        # Exige pelo menos algumas palavras.

        words = re.findall(
            r"\b[\wÀ-ÿ'-]+\b",
            stripped,
        )


        if len(words) < 4:

            return False


        return True


    def extract_claim_texts(
        self,
        answer: str,
    ) -> tuple[str, ...]:

        answer = str(
            answer
            or ""
        )


        claims: list[str] = []


        citation_only_pattern = re.compile(
            r"^\s*((?:\[S\d+\]\s*)+)$",
            re.IGNORECASE,
        )


        heading_pattern = re.compile(
            r"^\s*#{1,6}\s+"
        )


        bullet_pattern = re.compile(
            r"^\s*(?:[-*?]|\d+[.)])\s+"
        )


        leading_citations_pattern = re.compile(
            r"^\s*((?:\[S\d+\]\s*)+)",
            re.IGNORECASE,
        )


        # Indices dos claims factuais do ultimo
        # bloco de bullets.
        #
        # Isso permite:
        #
        # - Web2py ...
        # - CherryPy ...
        # - BeeWare ...
        #
        # [S7]
        #
        # => S7 sustenta os tres bullets.
        recent_bullet_claim_indices: list[int] = []


        def is_structural_narrative(
            text: str,
        ) -> bool:

            plain = re.sub(
                r"[*_`]",
                "",
                text,
            ).strip().lower()


            patterns = (
                r"^com base nas fontes",
                r"^com base nas evid[e?]ncias",
                r"^segue um resumo",
                r"^a seguir[, :]",
                r"^veja abaixo",
                r"^exemplos? de .*citados? nas fontes",
                r"^exemplos? de .*nas fontes",
                r"^fontes utilizadas",
                r"^refer[e?]ncias utilizadas",
            )


            return any(
                re.search(
                    pattern,
                    plain,
                    re.IGNORECASE,
                )
                for pattern in patterns
            )


        def is_short_structural_label(
            text: str,
        ) -> bool:

            plain = re.sub(
                r"[*_`]",
                "",
                text,
            ).strip()


            words = re.findall(
                r"\b[\w?-?'-]+\b",
                plain,
            )


            return bool(
                len(words) <= 7
                and not re.search(
                    r"[.!?]$",
                    plain,
                )
                and ":" not in plain
            )


        def append_claim(
            text: str,
            *,
            bullet_claim: bool = False,
        ) -> None:

            text = text.strip()


            if not self._is_claim_candidate(
                text
            ):

                return


            if is_structural_narrative(
                text
            ):

                return


            if text in claims:

                return


            claims.append(
                text
            )


            if bullet_claim:

                recent_bullet_claim_indices.append(
                    len(claims) - 1
                )

            else:

                recent_bullet_claim_indices.clear()


        for raw_line in answer.splitlines():

            stripped = raw_line.strip()


            if not stripped:
                continue


            # =================================================
            # HEADINGS
            # =================================================

            if heading_pattern.match(
                raw_line
            ):

                recent_bullet_claim_indices.clear()

                continue


            # =================================================
            # CITATION-ONLY LINE
            # =================================================

            citation_only_match = (
                citation_only_pattern
                .match(
                    stripped
                )
            )


            if citation_only_match:

                citation_block = (
                    citation_only_match
                    .group(1)
                    .strip()
                )


                # Se temos um grupo recente de bullets,
                # a citacao isolada sustenta o grupo inteiro.

                if recent_bullet_claim_indices:

                    for index in (
                        recent_bullet_claim_indices
                    ):

                        existing = claims[
                            index
                        ]


                        existing_ids = {
                            item.upper()
                            for item in
                            self.CITATION_PATTERN
                            .findall(
                                existing
                            )
                        }


                        new_ids = [
                            item.upper()
                            for item in
                            self.CITATION_PATTERN
                            .findall(
                                citation_block
                            )
                            if item.upper()
                            not in existing_ids
                        ]


                        if new_ids:

                            suffix = " ".join(
                                f"[{item}]"
                                for item in new_ids
                            )


                            claims[index] = (
                                existing.rstrip()
                                + " "
                                + suffix
                            )


                    recent_bullet_claim_indices.clear()

                    continue


                # Sem grupo de bullets:
                # anexa somente ao claim anterior.

                if claims:

                    existing = claims[-1]


                    existing_ids = {
                        item.upper()
                        for item in
                        self.CITATION_PATTERN
                        .findall(
                            existing
                        )
                    }


                    new_ids = [
                        item.upper()
                        for item in
                        self.CITATION_PATTERN
                        .findall(
                            citation_block
                        )
                        if item.upper()
                        not in existing_ids
                    ]


                    if new_ids:

                        suffix = " ".join(
                            f"[{item}]"
                            for item in new_ids
                        )


                        claims[-1] = (
                            existing.rstrip()
                            + " "
                            + suffix
                        )


                continue


            # =================================================
            # BULLET
            # =================================================

            is_bullet = bool(
                bullet_pattern.match(
                    raw_line
                )
            )


            line = (
                bullet_pattern.sub(
                    "",
                    raw_line,
                ).strip()
                if is_bullet
                else stripped
            )


            # Bullet curto usado apenas como label:
            #
            # - F?cil de aprender e poderosa
            #
            # nao conta como claim separado.

            if (
                is_bullet
                and is_short_structural_label(
                    line
                )
            ):

                recent_bullet_claim_indices.clear()

                continue


            # =================================================
            # SENTENCE SPLIT + CITATION ATTACHMENT
            # =================================================

            raw_parts = re.split(
                r"(?<=[.!?])\s+",
                line,
            )


            normalized_parts: list[str] = []


            for raw_part in raw_parts:

                part = raw_part.strip()


                if not part:
                    continue


                leading_match = (
                    leading_citations_pattern
                    .match(
                        part
                    )
                )


                if (
                    leading_match
                    and normalized_parts
                ):

                    citation_block = (
                        leading_match
                        .group(1)
                        .strip()
                    )


                    normalized_parts[-1] = (
                        normalized_parts[-1]
                        .rstrip()
                        + " "
                        + citation_block
                    )


                    remainder = (
                        part[
                            leading_match.end():
                        ]
                        .strip()
                    )


                    if remainder:

                        normalized_parts.append(
                            remainder
                        )


                    continue


                normalized_parts.append(
                    part
                )


            for part in normalized_parts:

                append_claim(
                    part,
                    bullet_claim=is_bullet,
                )


        return tuple(
            claims
        )


    def analyze(
        self,
        answer: str,
        sources: Any,
        minimum_coverage: float = 0.80,
    ) -> ClaimGroundingResult:

        source_ids = {
            str(
                source.source_id
            ).upper()
            for source in (
                sources
                or ()
            )
        }


        claim_texts = (
            self.extract_claim_texts(
                answer
            )
        )


        claims: list[
            GroundedClaim
        ] = []


        for index, text in enumerate(
            claim_texts,
            start=1,
        ):

            citation_ids = tuple(
                dict.fromkeys(
                    citation.upper()
                    for citation in
                    self.CITATION_PATTERN.findall(
                        text
                    )
                )
            )


            valid = tuple(
                citation
                for citation
                in citation_ids
                if citation
                in source_ids
            )


            invalid = tuple(
                citation
                for citation
                in citation_ids
                if citation
                not in source_ids
            )


            claim_type = (
                self.classify_claim_type(
                    text
                )
            )


            requires_citation = (
                self._requires_citation(
                    claim_type
                )
            )


            validly_cited = bool(
                valid
            ) and not bool(
                invalid
            )


            claims.append(
                GroundedClaim(

                    claim_id=
                        f"C{index}",

                    text=
                        text,

                    citation_ids=
                        citation_ids,

                    valid_citation_ids=
                        valid,

                    invalid_citation_ids=
                        invalid,

                    cited=
                        bool(
                            citation_ids
                        ),

                    validly_cited=
                        validly_cited,

                    claim_type=
                        claim_type,

                    requires_citation=
                        requires_citation,
                )
            )


        claim_count = len(
            claims
        )


        eligible_claims = [
            claim
            for claim in claims
            if claim.requires_citation
        ]


        eligible_claim_count = len(
            eligible_claims
        )


        cited_claim_count = sum(
            1
            for claim in eligible_claims
            if claim.cited
        )


        validly_cited_claim_count = sum(
            1
            for claim in eligible_claims
            if claim.validly_cited
        )


        invalid_claim_count = sum(
            1
            for claim in eligible_claims
            if claim.invalid_citation_ids
        )


        unsupported_claim_count = sum(
            1
            for claim in eligible_claims
            if not claim.validly_cited
        )


        citation_coverage = (
            cited_claim_count
            / eligible_claim_count
            if eligible_claim_count
            else 1.0
        )


        valid_citation_coverage = (
            validly_cited_claim_count
            / eligible_claim_count
            if eligible_claim_count
            else 1.0
        )


        # Grounding V1 mede cobertura estrutural.
        #
        # Ainda NAO e entailment semantico.
        # Isso vira Grounding V2 depois.

        grounding_score = (
            valid_citation_coverage
            if not invalid_claim_count
            else (
                valid_citation_coverage
                * 0.75
            )
        )


        grounded = bool(

            eligible_claim_count > 0

            and valid_citation_coverage
            >= minimum_coverage

            and invalid_claim_count
            == 0
        )


        return ClaimGroundingResult(

            claims=
                tuple(
                    claims
                ),

            claim_count=
                claim_count,

            cited_claim_count=
                cited_claim_count,

            validly_cited_claim_count=
                validly_cited_claim_count,

            unsupported_claim_count=
                unsupported_claim_count,

            invalid_claim_count=
                invalid_claim_count,

            citation_coverage=
                round(
                    citation_coverage,
                    4,
                ),

            valid_citation_coverage=
                round(
                    valid_citation_coverage,
                    4,
                ),

            grounding_score=
                round(
                    grounding_score,
                    4,
                ),

            grounded=
                grounded,
        )


claim_grounding_engine = (
    ClaimGroundingEngine()
)
