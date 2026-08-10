from __future__ import annotations

import re
from dataclasses import (
    asdict,
    dataclass,
)
from typing import Any
from urllib.parse import urlparse


HIGH_AUTHORITY_DOMAINS = {
    "openai.com",
    "python.org",
    "microsoft.com",
    "docs.python.org",
    "supabase.com",
    "docker.com",
    "nvidia.com",
    "canada.ca",
    "gc.ca",
    "ontario.ca",
    "who.int",
    "nih.gov",
    "cdc.gov",
    "sec.gov",
    "federalreserve.gov",
}


LOW_AUTHORITY_PATTERNS = (
    "pinterest.",
    "quora.",
    "facebook.",
    "instagram.",
    "tiktok.",
    "x.com",
    "twitter.",
)


@dataclass(frozen=True)
class Evidence:

    evidence_id: str

    rank: int

    title: str

    url: str

    domain: str

    snippet: str

    source_type: str

    authority_score: float

    relevance_score: float

    quality_score: float

    duplicate: bool = False

    blocked: bool = False

    block_reason: str | None = None

    def to_dict(self) -> dict:

        return asdict(self)


@dataclass(frozen=True)
class EvidenceSet:

    query: str

    items: tuple[Evidence, ...]

    unique_domains: int

    average_quality: float

    strongest_quality: float

    usable_count: int

    blocked_count: int

    duplicate_count: int

    def to_dict(self) -> dict:

        return {
            "query":
                self.query,

            "items": [
                item.to_dict()
                for item in self.items
            ],

            "unique_domains":
                self.unique_domains,

            "average_quality":
                self.average_quality,

            "strongest_quality":
                self.strongest_quality,

            "usable_count":
                self.usable_count,

            "blocked_count":
                self.blocked_count,

            "duplicate_count":
                self.duplicate_count,
        }


class EvidenceEngine:

    def _normalize_domain(
        self,
        value: str,
    ) -> str:

        domain = str(
            value or ""
        ).strip().lower()

        domain = domain.removeprefix(
            "www."
        )

        return domain


    def _domain_from_url(
        self,
        url: str,
    ) -> str:

        try:

            parsed = urlparse(
                url
            )

            return self._normalize_domain(
                parsed.hostname
                or ""
            )

        except Exception:

            return ""


    def _github_owner(
        self,
        url: str,
    ) -> str:

        try:

            parsed = urlparse(
                str(
                    url
                    or ""
                )
            )

            if (
                self._normalize_domain(
                    parsed.hostname
                    or ""
                )
                != "github.com"
            ):

                return ""


            parts = [
                part
                for part in (
                    parsed.path
                    or ""
                ).split("/")
                if part
            ]


            if not parts:

                return ""


            return parts[0].lower()


        except Exception:

            return ""


    def source_group(
        self,
        domain: str,
        url: str = "",
    ) -> str:

        domain = self._normalize_domain(
            domain
        )


        if not domain:

            return ""


        # ----------------------------------------------------
        # GitHub:
        # repositorios do mesmo owner pertencem
        # ao mesmo grupo editorial.
        # ----------------------------------------------------

        if domain == "github.com":

            owner = self._github_owner(
                url
            )


            if owner:

                return (
                    f"github:{owner}"
                )


            return "github.com"


        # ----------------------------------------------------
        # Government / public ecosystems
        # ----------------------------------------------------

        if domain.endswith(
            ".gc.ca"
        ):

            return "gc.ca"


        # ----------------------------------------------------
        # Known official ecosystems
        # ----------------------------------------------------

        known_roots = (
            "python.org",
            "openai.com",
            "microsoft.com",
            "supabase.com",
            "docker.com",
            "nvidia.com",
        )


        for root in known_roots:

            if (
                domain == root
                or domain.endswith(
                    "." + root
                )
            ):

                return root


        # ----------------------------------------------------
        # Generic fallback:
        #
        # agrupa subdominio simples ao dominio raiz
        # quando existe estrutura comum example.com.
        #
        # Nao e um Public Suffix List completo.
        # Essa melhoria vem posteriormente.
        # ----------------------------------------------------

        parts = domain.split(".")


        if len(parts) >= 3:

            common_second_level = {
                "co",
                "com",
                "org",
                "net",
                "gov",
                "ac",
            }


            if (
                len(parts) >= 3
                and parts[-2]
                in common_second_level
            ):

                return ".".join(
                    parts[-3:]
                )


            return ".".join(
                parts[-2:]
            )


        return domain


    def authority_score(
        self,
        domain: str,
        url: str = "",
    ) -> float:

        domain = self._normalize_domain(
            domain
        )


        if not domain:

            return 0.0


        # ====================================================
        # GITHUB CONTEXTUAL
        # ====================================================

        if domain == "github.com":

            owner = self._github_owner(
                url
            )


            official_owners = {
                "python",
                "openai",
                "microsoft",
                "supabase",
                "docker",
                "nvidia",
            }


            if owner in official_owners:

                return 0.95


            # GitHub e uma plataforma confiavel,
            # mas o conteudo pertence ao autor.
            return 0.55


        # ====================================================
        # EXACT / TRUSTED
        # ====================================================

        if domain in HIGH_AUTHORITY_DOMAINS:

            return 1.0


        # ====================================================
        # OFFICIAL SUBDOMAINS
        # ====================================================

        trusted_roots = (
            "python.org",
            "openai.com",
            "microsoft.com",
            "supabase.com",
            "docker.com",
            "nvidia.com",
        )


        if any(
            domain.endswith(
                "." + root
            )
            for root
            in trusted_roots
        ):

            return 0.95


        # ====================================================
        # GOVERNMENT / ACADEMIC
        # ====================================================

        if domain.endswith(
            ".gov"
        ):

            return 0.95


        if domain.endswith(
            ".gc.ca"
        ):

            return 0.95


        if domain.endswith(
            ".edu"
        ):

            return 0.90


        if domain.endswith(
            ".ac.uk"
        ):

            return 0.90


        # ====================================================
        # DOCS
        #
        # Docs so recebe bonus moderado se nao foi
        # reconhecido como ecossistema oficial acima.
        # ====================================================

        if domain.startswith(
            "docs."
        ):

            return 0.80


        # ====================================================
        # ENCYCLOPEDIA
        # ====================================================

        if domain.endswith(
            "wikipedia.org"
        ):

            return 0.70


        # ====================================================
        # SOCIAL / USER GENERATED
        # ====================================================

        if any(
            pattern in domain
            for pattern
            in LOW_AUTHORITY_PATTERNS
        ):

            return 0.25


        return 0.55


    def relevance_score(
        self,
        query: str,
        title: str,
        snippet: str,
    ) -> float:

        query_terms = {
            term
            for term in re.findall(
                r"[a-zA-ZÀ-ÿ0-9_]+",
                query.lower(),
            )
            if len(term) >= 3
        }

        if not query_terms:

            return 0.5


        text = (
            f"{title} {snippet}"
        ).lower()


        text_terms = set(
            re.findall(
                r"[a-zA-ZÀ-ÿ0-9_]+",
                text,
            )
        )


        overlap = len(
            query_terms.intersection(
                text_terms
            )
        )


        score = (
            overlap
            / max(
                len(query_terms),
                1,
            )
        )


        return round(
            min(
                max(
                    score,
                    0.0,
                ),
                1.0,
            ),
            4,
        )


    def quality_score(
        self,
        authority: float,
        relevance: float,
        rank: int,
    ) -> float:

        rank_bonus = max(
            0.0,
            1.0
            - (
                max(
                    rank,
                    1,
                )
                - 1
            ) * 0.08,
        )


        score = (
            authority * 0.50
            + relevance * 0.35
            + rank_bonus * 0.15
        )


        return round(
            min(
                max(
                    score,
                    0.0,
                ),
                1.0,
            ),
            4,
        )


    def build(
        self,
        query: str,
        results: list[dict[str, Any]],
    ) -> EvidenceSet:

        query = str(
            query or ""
        ).strip()


        evidence: list[
            Evidence
        ] = []


        seen_urls = set()


        for index, item in enumerate(
            results or [],
            start=1,
        ):

            if not isinstance(
                item,
                dict,
            ):
                continue


            url = str(
                item.get(
                    "url",
                    "",
                )
            ).strip()


            title = str(
                item.get(
                    "title",
                    "",
                )
            ).strip()


            snippet = str(
                item.get(
                    "snippet",
                    "",
                )
            ).strip()


            domain = (
                self._normalize_domain(
                    item.get(
                        "domain",
                        "",
                    )
                )
                or self._domain_from_url(
                    url
                )
            )


            duplicate = (
                bool(url)
                and url in seen_urls
            )


            if url:

                seen_urls.add(
                    url
                )


            blocked = False
            block_reason = None


            if not url:

                blocked = True
                block_reason = (
                    "missing_url"
                )


            if not domain:

                blocked = True
                block_reason = (
                    "missing_domain"
                )


            authority = (
                self.authority_score(
                    domain,
                    url=url,
                )
            )


            relevance = (
                self.relevance_score(
                    query=query,
                    title=title,
                    snippet=snippet,
                )
            )


            quality = (
                self.quality_score(
                    authority=authority,
                    relevance=relevance,
                    rank=index,
                )
            )


            evidence.append(
                Evidence(
                    evidence_id=
                        f"ev-{index}",

                    rank=index,

                    title=title,

                    url=url,

                    domain=domain,

                    snippet=snippet,

                    source_type=str(
                        item.get(
                            "source_type",
                            "web",
                        )
                    ),

                    authority_score=
                        authority,

                    relevance_score=
                        relevance,

                    quality_score=
                        quality,

                    duplicate=
                        duplicate,

                    blocked=
                        blocked,

                    block_reason=
                        block_reason,
                )
            )


        usable = [
            item
            for item in evidence
            if not item.blocked
            and not item.duplicate
        ]


        blocked_count = sum(
            1
            for item in evidence
            if item.blocked
        )


        duplicate_count = sum(
            1
            for item in evidence
            if item.duplicate
        )


        domains = {
            item.domain
            for item in usable
            if item.domain
        }


        qualities = [
            item.quality_score
            for item in usable
        ]


        average_quality = (
            sum(
                qualities
            )
            / len(
                qualities
            )
            if qualities
            else 0.0
        )


        strongest_quality = (
            max(
                qualities
            )
            if qualities
            else 0.0
        )


        return EvidenceSet(
            query=query,

            items=tuple(
                evidence
            ),

            unique_domains=
                len(domains),

            average_quality=
                round(
                    average_quality,
                    4,
                ),

            strongest_quality=
                round(
                    strongest_quality,
                    4,
                ),

            usable_count=
                len(usable),

            blocked_count=
                blocked_count,

            duplicate_count=
                duplicate_count,
        )


evidence_engine = EvidenceEngine()
