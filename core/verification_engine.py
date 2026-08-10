from __future__ import annotations

import re
from dataclasses import (
    asdict,
    dataclass,
)
from enum import Enum

from core.evidence_engine import (
    Evidence,
    EvidenceEngine,
    EvidenceSet,
)


class VerificationStatus(
    str,
    Enum,
):

    VERIFIED = "VERIFIED"

    PARTIALLY_VERIFIED = (
        "PARTIALLY_VERIFIED"
    )

    INSUFFICIENT_EVIDENCE = (
        "INSUFFICIENT_EVIDENCE"
    )

    CONFLICTING_EVIDENCE = (
        "CONFLICTING_EVIDENCE"
    )


@dataclass(frozen=True)
class VerificationResult:

    status: VerificationStatus

    confidence: float

    evidence_count: int

    independent_domains: int

    high_quality_count: int

    authority_count: int

    conflict_detected: bool

    coverage_score: float

    diversity_score: float

    quality_score: float

    reasons: tuple[str, ...]

    evidence_ids: tuple[str, ...]

    def to_dict(self) -> dict:

        data = asdict(
            self
        )

        data[
            "status"
        ] = self.status.value

        data[
            "reasons"
        ] = list(
            self.reasons
        )

        data[
            "evidence_ids"
        ] = list(
            self.evidence_ids
        )

        return data


class VerificationEngine:

    def _source_group(
        self,
        evidence: Evidence,
    ) -> str:

        engine = EvidenceEngine()

        return engine.source_group(
            domain=
                evidence.domain,

            url=
                evidence.url,
        )


    NEGATION_TERMS = {
        "not",
        "no",
        "never",
        "false",
        "incorrect",
        "nao",
        "não",
        "nunca",
        "falso",
        "incorreto",
        "errado",
        "refuted",
        "denied",
        "nega",
        "negou",
    }


    def _usable(
        self,
        evidence_set: EvidenceSet,
    ) -> list[Evidence]:

        return [
            item
            for item in evidence_set.items
            if not item.blocked
            and not item.duplicate
        ]


    def _tokens(
        self,
        text: str,
    ) -> set[str]:

        return {
            token
            for token in re.findall(
                r"[a-zA-ZÀ-ÿ0-9_]+",
                str(
                    text
                    or ""
                ).lower(),
            )
            if len(token) >= 3
        }


    def _negation_signature(
        self,
        text: str,
    ) -> bool:

        tokens = self._tokens(
            text
        )

        return bool(
            tokens.intersection(
                self.NEGATION_TERMS
            )
        )


    def _sentences(
        self,
        text: str,
    ) -> list[str]:

        text = str(
            text
            or ""
        ).strip()


        if not text:

            return []


        parts = re.split(
            r"[.!?;\n]+",
            text,
        )


        return [
            part.strip()
            for part in parts
            if part.strip()
        ]


    def _content_tokens(
        self,
        text: str,
    ) -> set[str]:

        tokens = self._tokens(
            text
        )


        stopwords = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "that",
            "this",
            "are",
            "was",
            "were",
            "have",
            "has",
            "had",
            "uma",
            "uns",
            "umas",
            "para",
            "com",
            "que",
            "por",
            "como",
            "dos",
            "das",
            "uma",
            "este",
            "esta",
            "isso",
            "isto",
        }


        return {
            token
            for token in tokens
            if token not in stopwords
            and token
                not in self.NEGATION_TERMS
        }


    def _sentence_conflict(
        self,
        left: str,
        right: str,
    ) -> bool:

        left_negative = (
            self._negation_signature(
                left
            )
        )


        right_negative = (
            self._negation_signature(
                right
            )
        )


        # Mesma polaridade nao e contradicao.
        if (
            left_negative
            == right_negative
        ):

            return False


        left_tokens = (
            self._content_tokens(
                left
            )
        )


        right_tokens = (
            self._content_tokens(
                right
            )
        )


        if (
            not left_tokens
            or not right_tokens
        ):

            return False


        shared = (
            left_tokens.intersection(
                right_tokens
            )
        )


        # Evita conflito baseado apenas
        # em uma ou duas palavras genericas.
        if len(shared) < 3:

            return False


        denominator = max(
            min(
                len(left_tokens),
                len(right_tokens),
            ),
            1,
        )


        containment = (
            len(shared)
            / denominator
        )


        union = (
            left_tokens.union(
                right_tokens
            )
        )


        jaccard = (
            len(shared)
            / max(
                len(union),
                1,
            )
        )


        # O V1 usava aproximadamente 0.35
        # sobre textos inteiros.
        #
        # O V2 exige frases realmente
        # descrevendo quase a mesma claim.
        return (
            containment >= 0.75
            and jaccard >= 0.55
        )


    def detect_conflict(
        self,
        evidence:
            list[Evidence],
    ) -> bool:

        """
        Conflict Detector V2.

        Regras:

        - fontes independentes;
        - evidencias utilizaveis;
        - comparacao frase a frase;
        - polaridade oposta;
        - >= 3 termos substantivos comuns;
        - alta sobreposicao lexical.

        Isso reduz falsos positivos causados
        por uma palavra "not/nao" aparecendo
        em qualquer lugar de um snippet longo.
        """


        for i, left in enumerate(
            evidence
        ):

            if left.quality_score < 0.45:

                continue


            left_text = (
                f"{left.title}. "
                f"{left.snippet}"
            )


            left_sentences = (
                self._sentences(
                    left_text
                )
            )


            for right in evidence[
                i + 1:
            ]:

                if (
                    self._source_group(
                        left
                    )
                    == self._source_group(
                        right
                    )
                ):

                    continue


                if right.quality_score < 0.45:

                    continue


                right_text = (
                    f"{right.title}. "
                    f"{right.snippet}"
                )


                right_sentences = (
                    self._sentences(
                        right_text
                    )
                )


                for left_sentence in (
                    left_sentences
                ):

                    for right_sentence in (
                        right_sentences
                    ):

                        if self._sentence_conflict(
                            left_sentence,
                            right_sentence,
                        ):

                            return True


        return False


    def verify(
        self,
        evidence_set:
            EvidenceSet,
    ) -> VerificationResult:

        usable = self._usable(
            evidence_set
        )


        evidence_count = len(
            usable
        )


        source_groups = {
            self._source_group(
                item
            )
            for item in usable
            if self._source_group(
                item
            )
        }


        independent_domains = len(
            source_groups
        )


        high_quality = [
            item
            for item in usable
            if item.quality_score >= 0.70
        ]


        high_authority = [
            item
            for item in usable
            if item.authority_score >= 0.85
        ]


        # ====================================================
        # SCORES
        # ====================================================

        # ====================================================
        # SOURCE CONCENTRATION V2
        #
        # Evidencias adicionais do mesmo grupo ajudam,
        # mas possuem peso reduzido.
        #
        # 1 grupo + 10 paginas nao equivale a
        # 3 fontes independentes.
        # ====================================================

        repeated_evidence = max(
            evidence_count
            - independent_domains,
            0,
        )


        effective_coverage = (
            independent_domains
            + min(
                repeated_evidence * 0.20,
                1.0,
            )
        )


        coverage_score = min(
            effective_coverage / 3.0,
            1.0,
        )


        diversity_score = min(
            independent_domains / 3.0,
            1.0,
        )


        quality_score = (
            sum(
                item.quality_score
                for item in usable
            )
            / evidence_count
            if evidence_count
            else 0.0
        )


        conflict = (
            self.detect_conflict(
                usable
            )
        )


        confidence = (
            coverage_score * 0.30
            + diversity_score * 0.25
            + quality_score * 0.35
            + min(
                len(
                    high_authority
                ) / 2.0,
                1.0,
            ) * 0.10
        )


        confidence = round(
            min(
                max(
                    confidence,
                    0.0,
                ),
                1.0,
            ),
            4,
        )


        reasons: list[str] = []


        if evidence_count == 0:

            reasons.append(
                "no_usable_evidence"
            )


        if evidence_count < 2:

            reasons.append(
                "low_evidence_count"
            )


        if independent_domains < 2:

            reasons.append(
                "low_source_diversity"
            )


        if not high_quality:

            reasons.append(
                "no_high_quality_evidence"
            )


        if not high_authority:

            reasons.append(
                "no_high_authority_source"
            )


        if conflict:

            reasons.append(
                "conflicting_evidence"
            )


        # ====================================================
        # STATUS
        # ====================================================

        if conflict:

            status = (
                VerificationStatus
                .CONFLICTING_EVIDENCE
            )


        elif (
            evidence_count < 2
            or confidence < 0.45
        ):

            status = (
                VerificationStatus
                .INSUFFICIENT_EVIDENCE
            )


        elif (
            evidence_count >= 3
            and independent_domains >= 2
            and len(
                high_quality
            ) >= 2
            and confidence >= 0.72
        ):

            status = (
                VerificationStatus
                .VERIFIED
            )


        else:

            status = (
                VerificationStatus
                .PARTIALLY_VERIFIED
            )


        return VerificationResult(

            status=status,

            confidence=
                confidence,

            evidence_count=
                evidence_count,

            independent_domains=
                independent_domains,

            high_quality_count=
                len(
                    high_quality
                ),

            authority_count=
                len(
                    high_authority
                ),

            conflict_detected=
                conflict,

            coverage_score=
                round(
                    coverage_score,
                    4,
                ),

            diversity_score=
                round(
                    diversity_score,
                    4,
                ),

            quality_score=
                round(
                    quality_score,
                    4,
                ),

            reasons=tuple(
                reasons
            ),

            evidence_ids=tuple(
                item.evidence_id
                for item in usable
            ),
        )


verification_engine = (
    VerificationEngine()
)
