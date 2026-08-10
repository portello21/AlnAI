from __future__ import annotations

import re
from dataclasses import (
    asdict,
    dataclass,
)

from core.research_engine import (
    ResearchEngine,
)


@dataclass(frozen=True)
class MultiResearchResult:

    rank: int

    title: str

    url: str

    snippet: str

    domain: str

    source_type: str

    best_rank: int

    query_hits: int

    matched_queries: tuple[str, ...]

    def to_dict(self) -> dict:

        data = asdict(
            self
        )

        data[
            "matched_queries"
        ] = list(
            self.matched_queries
        )

        return data


@dataclass(frozen=True)
class MultiResearchResponse:

    success: bool

    original_query: str

    expanded_queries: tuple[str, ...]

    results: tuple[MultiResearchResult, ...]

    total_raw_results: int

    duplicate_results_removed: int

    successful_queries: int

    failed_queries: int

    error: str | None = None

    def to_dict(self) -> dict:

        return {
            "success":
                self.success,

            "original_query":
                self.original_query,

            "expanded_queries":
                list(
                    self.expanded_queries
                ),

            "results": [
                item.to_dict()
                for item in self.results
            ],

            "result_count":
                len(
                    self.results
                ),

            "total_raw_results":
                self.total_raw_results,

            "duplicate_results_removed":
                self.duplicate_results_removed,

            "successful_queries":
                self.successful_queries,

            "failed_queries":
                self.failed_queries,

            "error":
                self.error,
        }


class QueryExpander:

    FRESHNESS_TERMS = {
        "latest",
        "recent",
        "current",
        "today",
        "news",
        "novo",
        "nova",
        "novos",
        "novas",
        "recente",
        "recentes",
        "atual",
        "atuais",
        "hoje",
        "noticia",
        "noticias",
        "notícia",
        "notícias",
    }


    TECH_TERMS = {
        "python",
        "api",
        "docker",
        "supabase",
        "programming",
        "programacao",
        "programação",
        "software",
        "library",
        "framework",
        "documentation",
        "documentacao",
        "documentação",
        "github",
        "code",
        "codigo",
        "código",
    }


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
            if token
        }


    def expand(
        self,
        query: str,
        max_queries: int = 3,
    ) -> tuple[str, ...]:

        query = " ".join(
            str(
                query
                or ""
            ).split()
        )


        if not query:

            return ()


        max_queries = max(
            1,
            min(
                int(
                    max_queries
                ),
                5,
            ),
        )


        tokens = self._tokens(
            query
        )


        candidates = [
            query
        ]


        # ====================================================
        # PRIMARY / OFFICIAL SOURCE
        # ====================================================

        candidates.append(
            f"{query} official source"
        )


        # ====================================================
        # CONTEXT-SPECIFIC EXPANSION
        # ====================================================

        if tokens.intersection(
            self.TECH_TERMS
        ):

            candidates.append(
                f"{query} official documentation"
            )


        elif tokens.intersection(
            self.FRESHNESS_TERMS
        ):

            candidates.append(
                f"{query} latest authoritative sources"
            )


        else:

            candidates.append(
                f"{query} authoritative source"
            )


        # ====================================================
        # DEDUPE
        # ====================================================

        result = []

        seen = set()


        for candidate in candidates:

            normalized = (
                candidate
                .strip()
                .lower()
            )

            if not normalized:

                continue


            if normalized in seen:

                continue


            seen.add(
                normalized
            )

            result.append(
                candidate.strip()
            )


            if (
                len(result)
                >= max_queries
            ):

                break


        return tuple(
            result
        )


class MultiResearchEngine:

    def __init__(
        self,
        research_engine:
            ResearchEngine | None = None,
    ):

        self.research_engine = (
            research_engine
            or ResearchEngine()
        )

        self.query_expander = (
            QueryExpander()
        )


    def search(
        self,
        query: str,
        max_queries: int = 3,
        results_per_query: int = 5,
        max_merged_results: int = 10,
        region: str = "wt-wt",
        safesearch: str = "moderate",
        timelimit: str | None = None,
    ) -> MultiResearchResponse:

        query = str(
            query
            or ""
        ).strip()


        if not query:

            return MultiResearchResponse(
                success=False,

                original_query="",

                expanded_queries=(),

                results=(),

                total_raw_results=0,

                duplicate_results_removed=0,

                successful_queries=0,

                failed_queries=0,

                error=
                    "Query vazia.",
            )


        expanded_queries = (
            self.query_expander.expand(
                query=query,

                max_queries=
                    max_queries,
            )
        )


        if not expanded_queries:

            return MultiResearchResponse(
                success=False,

                original_query=
                    query,

                expanded_queries=(),

                results=(),

                total_raw_results=0,

                duplicate_results_removed=0,

                successful_queries=0,

                failed_queries=0,

                error=
                    "Nenhuma query expandida.",
            )


        results_per_query = max(
            1,
            min(
                int(
                    results_per_query
                ),
                10,
            ),
        )


        max_merged_results = max(
            1,
            min(
                int(
                    max_merged_results
                ),
                30,
            ),
        )


        # URL -> accumulated state
        merged: dict[
            str,
            dict,
        ] = {}


        total_raw_results = 0

        successful_queries = 0

        failed_queries = 0


        # ====================================================
        # EXECUTE QUERIES
        # ====================================================

        for expanded_query in (
            expanded_queries
        ):

            response = (
                self.research_engine.search(
                    query=
                        expanded_query,

                    max_results=
                        results_per_query,

                    region=
                        region,

                    safesearch=
                        safesearch,

                    timelimit=
                        timelimit,
                )
            )


            if not response.success:

                failed_queries += 1

                continue


            successful_queries += 1


            for item in response.results:

                total_raw_results += 1


                existing = merged.get(
                    item.url
                )


                if existing is None:

                    merged[
                        item.url
                    ] = {
                        "title":
                            item.title,

                        "url":
                            item.url,

                        "snippet":
                            item.snippet,

                        "domain":
                            item.domain,

                        "source_type":
                            item.source_type,

                        "best_rank":
                            item.rank,

                        "matched_queries": [
                            expanded_query
                        ],
                    }


                else:

                    existing[
                        "best_rank"
                    ] = min(
                        existing[
                            "best_rank"
                        ],
                        item.rank,
                    )


                    if (
                        expanded_query
                        not in existing[
                            "matched_queries"
                        ]
                    ):

                        existing[
                            "matched_queries"
                        ].append(
                            expanded_query
                        )


                    # Prefer longer snippet.
                    if (
                        len(
                            item.snippet
                        )
                        > len(
                            existing[
                                "snippet"
                            ]
                        )
                    ):

                        existing[
                            "snippet"
                        ] = item.snippet


                    # Prefer richer title.
                    if (
                        len(
                            item.title
                        )
                        > len(
                            existing[
                                "title"
                            ]
                        )
                    ):

                        existing[
                            "title"
                        ] = item.title


        # ====================================================
        # RANK MERGED RESULTS
        #
        # More query hits first, then best original rank.
        # ====================================================

        merged_rows = list(
            merged.values()
        )


        merged_rows.sort(
            key=lambda item: (
                -len(
                    item[
                        "matched_queries"
                    ]
                ),
                item[
                    "best_rank"
                ],
                item[
                    "domain"
                ],
            )
        )


        merged_rows = merged_rows[
            :max_merged_results
        ]


        final_results = []


        for index, item in enumerate(
            merged_rows,
            start=1,
        ):

            final_results.append(
                MultiResearchResult(
                    rank=index,

                    title=
                        item[
                            "title"
                        ],

                    url=
                        item[
                            "url"
                        ],

                    snippet=
                        item[
                            "snippet"
                        ],

                    domain=
                        item[
                            "domain"
                        ],

                    source_type=
                        item[
                            "source_type"
                        ],

                    best_rank=
                        item[
                            "best_rank"
                        ],

                    query_hits=
                        len(
                            item[
                                "matched_queries"
                            ]
                        ),

                    matched_queries=
                        tuple(
                            item[
                                "matched_queries"
                            ]
                        ),
                )
            )


        duplicate_results_removed = max(
            total_raw_results
            - len(
                merged
            ),
            0,
        )


        success = bool(
            final_results
        )


        return MultiResearchResponse(
            success=success,

            original_query=
                query,

            expanded_queries=
                expanded_queries,

            results=tuple(
                final_results
            ),

            total_raw_results=
                total_raw_results,

            duplicate_results_removed=
                duplicate_results_removed,

            successful_queries=
                successful_queries,

            failed_queries=
                failed_queries,

            error=(
                None
                if success
                else
                "Nenhuma pesquisa retornou resultados."
            ),
        )


query_expander = (
    QueryExpander()
)

multi_research_engine = (
    MultiResearchEngine()
)
