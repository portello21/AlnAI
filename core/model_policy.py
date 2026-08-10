from __future__ import annotations

from dataclasses import dataclass


LOCAL_MODEL = "qwen3"
FAST_MODEL = "deepseek-chat"
REASONING_MODEL = "deepseek-reasoner"


@dataclass
class RoutingDecision:

    requested_model: str
    selected_model: str

    route_mode: str

    complexity_score: float
    reasoning_score: float
    privacy_score: float

    local_available: bool

    reason: str

    def as_dict(self) -> dict:

        return {
            "requested_model":
                self.requested_model,

            "selected_model":
                self.selected_model,

            "route_mode":
                self.route_mode,

            "complexity_score":
                self.complexity_score,

            "reasoning_score":
                self.reasoning_score,

            "privacy_score":
                self.privacy_score,

            "local_available":
                self.local_available,

            "reason":
                self.reason,
        }


class IntelligentModelRouter:
    """
    Router deterministico V2.

    Nao chama LLM para decidir.
    Isso evita custo, latencia e loop de routing.

    A decisao considera:
    - agente
    - texto da solicitacao
    - privacidade
    - complexidade
    - necessidade de reasoning
    - disponibilidade local
    """

    REASONING_TERMS = {
        "analise",
        "analisar",
        "compare",
        "comparar",
        "calcule",
        "calcular",
        "estrategia",
        "estratégia",
        "planejamento",
        "projecao",
        "projeção",
        "otimize",
        "otimizar",
        "arquitetura",
        "debug",
        "diagnostico",
        "diagnóstico",
        "investigue",
        "investigar",
        "causa",
        "porque",
        "por que",
        "raciocine",
        "reason",
        "reasoning",
        "tradeoff",
        "trade-off",
        "risco",
        "cenarios",
        "cenários",
    }

    COMPLEX_TERMS = {
        "passo a passo",
        "detalhado",
        "detalhada",
        "completo",
        "completa",
        "profundo",
        "profunda",
        "arquitetura",
        "sistema",
        "multiagente",
        "pipeline",
        "financeiro",
        "financeira",
        "investimento",
        "business",
        "negocio",
        "negócio",
        "codigo",
        "código",
        "programacao",
        "programação",
        "erro",
        "bug",
        "docker",
        "python",
        "powershell",
        "api",
    }

    PRIVACY_TERMS = {
        "privado",
        "privada",
        "confidencial",
        "segredo",
        "senha",
        "password",
        "token",
        "api key",
        "api_key",
        "documento pessoal",
        "dados pessoais",
        "local apenas",
        "somente local",
        "nao envie",
        "não envie",
        "offline",
    }

    SIMPLE_AGENT_IDS = {
        "personal",
        "english",
        "coach",
    }

    REASONING_AGENT_IDS = {
        "finance",
        "tech",
        "business",
    }


    def _contains_any(
        self,
        text: str,
        terms: set[str],
    ) -> int:

        return sum(
            1
            for term in terms
            if term in text
        )


    def analyze(
        self,
        agent_id: str,
        user_query: str,
    ) -> dict:

        text = (
            user_query
            or ""
        ).strip().lower()

        words = text.split()

        reasoning_hits = (
            self._contains_any(
                text,
                self.REASONING_TERMS,
            )
        )

        complexity_hits = (
            self._contains_any(
                text,
                self.COMPLEX_TERMS,
            )
        )

        privacy_hits = (
            self._contains_any(
                text,
                self.PRIVACY_TERMS,
            )
        )


        # ----------------------------------------------------
        # LENGTH SIGNAL
        # ----------------------------------------------------

        length_score = min(
            len(words) / 120.0,
            1.0,
        )


        # ----------------------------------------------------
        # REASONING SCORE
        # ----------------------------------------------------

        reasoning_score = min(
            reasoning_hits * 0.20
            + (
                0.35
                if agent_id
                in self.REASONING_AGENT_IDS
                else 0.0
            )
            + length_score * 0.25,
            1.0,
        )


        # ----------------------------------------------------
        # COMPLEXITY SCORE
        # ----------------------------------------------------

        complexity_score = min(
            complexity_hits * 0.12
            + reasoning_hits * 0.10
            + length_score * 0.35,
            1.0,
        )


        # ----------------------------------------------------
        # PRIVACY SCORE
        # ----------------------------------------------------

        privacy_score = min(
            privacy_hits * 0.35,
            1.0,
        )


        return {
            "complexity_score":
                round(
                    complexity_score,
                    4,
                ),

            "reasoning_score":
                round(
                    reasoning_score,
                    4,
                ),

            "privacy_score":
                round(
                    privacy_score,
                    4,
                ),

            "reasoning_hits":
                reasoning_hits,

            "complexity_hits":
                complexity_hits,

            "privacy_hits":
                privacy_hits,

            "word_count":
                len(words),
        }


    def decide(
        self,
        agent_id: str,
        user_query: str,
        requested_model: str,
        local_available: bool,
    ) -> RoutingDecision:

        analysis = self.analyze(
            agent_id=agent_id,
            user_query=user_query,
        )

        complexity = analysis[
            "complexity_score"
        ]

        reasoning = analysis[
            "reasoning_score"
        ]

        privacy = analysis[
            "privacy_score"
        ]


        # ====================================================
        # 1. DOCUMENT AGENT
        #
        # Mantemos local por padrao.
        # ====================================================

        if agent_id == "document":

            return RoutingDecision(
                requested_model=
                    requested_model,

                selected_model=
                    (
                        LOCAL_MODEL
                        if local_available
                        else FAST_MODEL
                    ),

                route_mode=
                    (
                        "local"
                        if local_available
                        else "fast"
                    ),

                complexity_score=
                    complexity,

                reasoning_score=
                    reasoning,

                privacy_score=
                    privacy,

                local_available=
                    local_available,

                reason=
                    (
                        "document_agent_local"
                        if local_available
                        else
                        "document_local_unavailable"
                    ),
            )


        # ====================================================
        # 2. PRIVACY
        # ====================================================

        if (
            privacy >= 0.35
            and local_available
        ):

            return RoutingDecision(
                requested_model=
                    requested_model,

                selected_model=
                    LOCAL_MODEL,

                route_mode=
                    "local",

                complexity_score=
                    complexity,

                reasoning_score=
                    reasoning,

                privacy_score=
                    privacy,

                local_available=
                    local_available,

                reason=
                    "privacy_preferred_local",
            )


        # ====================================================
        # 3. HIGH REASONING
        # ====================================================

        if (
            reasoning >= 0.55
            or complexity >= 0.65
        ):

            return RoutingDecision(
                requested_model=
                    requested_model,

                selected_model=
                    REASONING_MODEL,

                route_mode=
                    "reasoning",

                complexity_score=
                    complexity,

                reasoning_score=
                    reasoning,

                privacy_score=
                    privacy,

                local_available=
                    local_available,

                reason=
                    "high_reasoning_or_complexity",
            )


        # ====================================================
        # 4. REASONING AGENT + MODERATE COMPLEXITY
        # ====================================================

        if (
            agent_id
            in self.REASONING_AGENT_IDS
            and (
                reasoning >= 0.30
                or complexity >= 0.30
            )
        ):

            return RoutingDecision(
                requested_model=
                    requested_model,

                selected_model=
                    REASONING_MODEL,

                route_mode=
                    "reasoning",

                complexity_score=
                    complexity,

                reasoning_score=
                    reasoning,

                privacy_score=
                    privacy,

                local_available=
                    local_available,

                reason=
                    "specialist_reasoning_agent",
            )


        # ====================================================
        # 5. EXPLICIT LOCAL REQUEST
        # ====================================================

        normalized_requested = (
            requested_model
            or ""
        ).strip().lower()

        if (
            "qwen3"
            in normalized_requested
            and local_available
        ):

            return RoutingDecision(
                requested_model=
                    requested_model,

                selected_model=
                    LOCAL_MODEL,

                route_mode=
                    "local",

                complexity_score=
                    complexity,

                reasoning_score=
                    reasoning,

                privacy_score=
                    privacy,

                local_available=
                    local_available,

                reason=
                    "requested_local_model",
            )


        # ====================================================
        # 6. DEFAULT FAST
        # ====================================================

        return RoutingDecision(
            requested_model=
                requested_model,

            selected_model=
                FAST_MODEL,

            route_mode=
                "fast",

            complexity_score=
                complexity,

            reasoning_score=
                reasoning,

            privacy_score=
                privacy,

            local_available=
                local_available,

            reason=
                "default_fast_route",
        )
