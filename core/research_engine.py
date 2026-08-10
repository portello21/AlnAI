from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)
from typing import Any
from urllib.parse import (
    urlparse,
    urlunparse,
)

from ddgs import DDGS


@dataclass(frozen=True)
class ResearchResult:

    rank: int

    title: str

    url: str

    snippet: str

    domain: str

    source_type: str = "web"

    def to_dict(self) -> dict:

        return asdict(
            self
        )


@dataclass(frozen=True)
class ResearchResponse:

    success: bool

    query: str

    results: tuple[ResearchResult, ...]

    error: str | None = None

    provider: str = "ddgs"

    def to_dict(self) -> dict:

        return {
            "success":
                self.success,

            "query":
                self.query,

            "results": [
                item.to_dict()
                for item in self.results
            ],

            "result_count":
                len(self.results),

            "error":
                self.error,

            "provider":
                self.provider,
        }


class ResearchEngine:

    def __init__(
        self,
        timeout_seconds: int = 8,
    ):

        self.timeout_seconds = max(
            2,
            int(timeout_seconds),
        )


    def _normalize_url(
        self,
        value: Any,
    ) -> str:

        url = str(
            value or ""
        ).strip()

        if not url:

            return ""


        try:

            parsed = urlparse(
                url
            )


            if parsed.scheme not in {
                "http",
                "https",
            }:

                return ""


            if not parsed.netloc:

                return ""


            hostname = (
                parsed.hostname
                or ""
            ).strip().lower()


            if (
                not hostname
                or "." not in hostname
            ):

                return ""


            # Remove fragments.
            fragment = ""


            # Algumas engines retornam lixo de tracking
            # ou caracteres soltos no final da URL.
            path = (
                parsed.path
                or ""
            ).strip()


            query = (
                parsed.query
                or ""
            ).strip()


            # Rejeita caminhos claramente corrompidos.
            suspicious_only = set(
                "?/:;#"
            )


            if (
                path
                and set(path)
                <= suspicious_only
            ):

                path = ""


            if (
                query
                and set(query)
                <= suspicious_only
            ):

                query = ""


            normalized = urlunparse(
                (
                    parsed.scheme.lower(),
                    parsed.netloc.lower(),
                    path,
                    parsed.params,
                    query,
                    fragment,
                )
            ).strip()


            if len(normalized) > 2048:

                return ""


            return normalized


        except Exception:

            return ""


    def _domain(
        self,
        url: str,
    ) -> str:

        try:

            return (
                urlparse(url)
                .netloc
                .lower()
                .removeprefix("www.")
            )

        except Exception:

            return ""


    def search(
        self,
        query: str,
        max_results: int = 5,
        region: str = "wt-wt",
        safesearch: str = "moderate",
        timelimit: str | None = None,
    ) -> ResearchResponse:

        query = str(
            query or ""
        ).strip()

        if not query:

            return ResearchResponse(
                success=False,
                query="",
                results=(),
                error="Query vazia.",
            )


        max_results = max(
            1,
            min(
                int(max_results),
                10,
            ),
        )


        try:

            client = DDGS(
                timeout=
                    self.timeout_seconds
            )

            raw_results = client.text(
                query=query,
                region=region,
                safesearch=safesearch,
                timelimit=timelimit,
                max_results=
                    max_results,
                backend="auto",
            )


            normalized: list[
                ResearchResult
            ] = []

            seen_urls = set()


            for item in (
                raw_results
                or []
            ):

                if not isinstance(
                    item,
                    dict,
                ):
                    continue


                url = self._normalize_url(
                    item.get(
                        "href"
                    )
                    or item.get(
                        "url"
                    )
                )


                if not url:

                    continue


                if url in seen_urls:

                    continue


                seen_urls.add(
                    url
                )


                title = str(
                    item.get(
                        "title",
                        "",
                    )
                ).strip()


                snippet = str(
                    item.get(
                        "body",
                        "",
                    )
                    or item.get(
                        "snippet",
                        "",
                    )
                    or item.get(
                        "description",
                        "",
                    )
                ).strip()


                normalized.append(
                    ResearchResult(
                        rank=
                            len(
                                normalized
                            ) + 1,

                        title=
                            title,

                        url=
                            url,

                        snippet=
                            snippet,

                        domain=
                            self._domain(
                                url
                            ),
                    )
                )


                if (
                    len(
                        normalized
                    )
                    >= max_results
                ):
                    break


            if not normalized:

                return ResearchResponse(
                    success=False,
                    query=query,
                    results=(),
                    error=(
                        "Nenhum resultado "
                        "de pesquisa encontrado."
                    ),
                )


            return ResearchResponse(
                success=True,
                query=query,
                results=tuple(
                    normalized
                ),
            )


        except Exception as exc:

            return ResearchResponse(
                success=False,
                query=query,
                results=(),
                error=str(
                    exc
                ),
            )


research_engine = ResearchEngine()
