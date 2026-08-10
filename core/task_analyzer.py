from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TaskAnalysis:
    query: str
    complexity: str
    needs_planning: bool
    needs_research: bool
    needs_tools: bool
    needs_calculation: bool
    needs_code: bool
    needs_verification: bool
    multi_step: bool
    score: int
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return data


RESEARCH_PATTERNS = (
    r"\bpesquis",
    r"\bprocure\b",
    r"\bbusque\b",
    r"\bsearch\b",
    r"\bresearch\b",
    r"\bnot[ií]cias?\b",
    r"\batualizad",
    r"\bmais recente\b",
    r"\blatest\b",
    r"\bpre[cç]o",
    r"\bcota[cç][aã]o",
    r"\bweather\b",
    r"\bclima\b",
)

CALCULATION_PATTERNS = (
    r"\bcalcule\b",
    r"\bcalcular\b",
    r"\bquanto custa\b",
    r"\bquanto daria\b",
    r"\bporcentagem\b",
    r"\bpercentual\b",
    r"\bjuros\b",
    r"\bparcel",
    r"\bsimule\b",
    r"\bsimula[cç][aã]o\b",
)

# ============================================================
# CODE INTENT V2
#
# Mencionar uma tecnologia nao significa que precisamos
# analisar ou executar codigo.
# ============================================================

CODE_ARTIFACT_PATTERNS = (
    r"\bc[o?]digo\b",
    r"\bscript\b",
    r"\btraceback\b",
    r"\bstack trace\b",
    r"\bsyntaxerror\b",
    r"\btypeerror\b",
    r"\bvalueerror\b",
    r"\bexception\b",
    r"\bbug\b",
)


CODE_DEBUG_PATTERNS = (
    r"\bdebug(?:ue|ar|ando)?\b",
    r"\bcorrija\b",
    r"\bcorrigir\b",
    r"\bconserte\b",
    r"\bconsertar\b",
    r"\brefatore\b",
    r"\brefatorar\b",
)


CODE_EXECUTION_PATTERNS = (
    r"\bexecute\b",
    r"\bexecutar\b",
    r"\brode\b",
    r"\brodar\b",
    r"\bteste\b",
    r"\btestar\b",
    r"\bcompile\b",
    r"\bcompilar\b",
)


CODE_CREATION_PATTERNS = (
    r"\bescreva\b",
    r"\bcrie\b",
    r"\bcriar\b",
    r"\bgere\b",
    r"\bgerar\b",
    r"\bimplemente\b",
    r"\bimplementar\b",
    r"\bmodifique\b",
    r"\bmodificar\b",
)


CODE_OBJECT_PATTERNS = (
    r"\bc[o?]digo\b",
    r"\bscript\b",
    r"\bfun[c?][a?]o\b",
    r"\bclasse\b",
    r"\bclass\b",
    r"\bm[e?]todo\b",
    r"\bprograma\b",
    r"\bendpoint\b",
    r"\barquivo\s+\.?(?:py|js|ts|ps1)\b",
)


CODE_ERROR_CONTEXT_PATTERNS = (
    r"\berro\b",
    r"\bfalha\b",
    r"\bexception\b",
    r"\btraceback\b",
    r"\bn[a?]o funciona\b",
    r"\bn[a?]o est[a?] funcionando\b",
    r"\bquebr(?:ou|ado)\b",
)


TECH_TERMS = (
    r"\bpython\b",
    r"\bpowershell\b",
    r"\bjavascript\b",
    r"\btypescript\b",
    r"\bapi\b",
    r"\bfastapi\b",
    r"\bflask\b",
    r"\bdjango\b",
    r"\breact\b",
    r"\bnode(?:\.js)?\b",
)


VERIFICATION_PATTERNS = (
    r"\bverifique\b",
    r"\bconfirme\b",
    r"\bvalide\b",
    r"\bcompare\b",
    r"\bconfira\b",
    r"\bprove\b",
    r"\bcheck\b",
    r"\bverify\b",
    r"\bvalidate\b",
)

PLANNING_PATTERNS = (
    r"\bplano\b",
    r"\bplanej",
    r"\bpasso a passo\b",
    r"\bestrat[eé]gia\b",
    r"\broadmap\b",
    r"\bimplemente\b",
    r"\bimplementar\b",
    r"\bconstrua\b",
    r"\bcrie um sistema\b",
    r"\barquitetura\b",
    r"\botimize\b",
    r"\bmelhore\b",
)

MULTISTEP_PATTERNS = (
    r"\bprimeiro\b.+\bdepois\b",
    r"\bdepois\b.+\bent[aã]o\b",
    r"\be depois\b",
    r"\bem seguida\b",
    r"\bpassos\b",
    r"\betapas\b",
    r"\bdo in[ií]cio ao fim\b",
)


def _matches_any(
    text: str,
    patterns: tuple[str, ...],
) -> bool:

    return any(
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for pattern in patterns
    )


def analyze_task(query: str) -> TaskAnalysis:

    original = str(query or "").strip()
    text = original.lower()

    if not text:
        return TaskAnalysis(
            query=original,
            complexity="simple",
            needs_planning=False,
            needs_research=False,
            needs_tools=False,
            needs_calculation=False,
            needs_code=False,
            needs_verification=False,
            multi_step=False,
            score=0,
            reasons=(),
        )

    needs_research = _matches_any(
        text,
        RESEARCH_PATTERNS,
    )

    needs_calculation = _matches_any(
        text,
        CALCULATION_PATTERNS,
    )

    code_artifact = _matches_any(
        text,
        CODE_ARTIFACT_PATTERNS,
    )

    code_debug = _matches_any(
        text,
        CODE_DEBUG_PATTERNS,
    )

    code_execution = _matches_any(
        text,
        CODE_EXECUTION_PATTERNS,
    )

    code_creation = _matches_any(
        text,
        CODE_CREATION_PATTERNS,
    )

    code_object = _matches_any(
        text,
        CODE_OBJECT_PATTERNS,
    )

    code_error_context = _matches_any(
        text,
        CODE_ERROR_CONTEXT_PATTERNS,
    )

    tech_term = _matches_any(
        text,
        TECH_TERMS,
    )


    # ========================================================
    # CODE INTENT V2
    # ========================================================
    #
    # "Python", "API", "JavaScript" etc. isoladamente
    # sao apenas assuntos tecnicos.
    #
    # Intent de codigo requer artefato/contexto de codigo
    # ou uma acao clara de criar, executar, testar,
    # corrigir ou depurar codigo.
    # ========================================================

    needs_code = bool(

        # Debug/correcao de algo relacionado a codigo.
        (
            code_debug
            and (
                code_artifact
                or code_object
                or code_error_context
                or tech_term
            )
        )

        # Execucao/teste exige objeto programavel.
        or (
            code_execution
            and (
                code_artifact
                or code_object
                or tech_term
            )
        )

        # Criacao/modificacao exige objeto ou tecnologia.
        or (
            code_creation
            and (
                code_artifact
                or code_object
                or tech_term
            )
        )

        # Traceback/exception/erros explicitamente
        # vinculados a um artefato de codigo.
        or (
            code_artifact
            and code_error_context
        )

        # Alguns artefatos sao sinais fortes por si so.
        or _matches_any(
            text,
            (
                r"\btraceback\b",
                r"\bstack trace\b",
                r"\bsyntaxerror\b",
                r"\btypeerror\b",
                r"\bvalueerror\b",
            ),
        )
    )


    needs_verification = _matches_any(
        text,
        VERIFICATION_PATTERNS,
    )

    explicit_planning = _matches_any(
        text,
        PLANNING_PATTERNS,
    )

    multi_step = _matches_any(
        text,
        MULTISTEP_PATTERNS,
    )

    reasons: list[str] = []
    score = 0

    if needs_research:
        score += 2
        reasons.append("research")

    if needs_calculation:
        score += 1
        reasons.append("calculation")

    if needs_code:
        score += 1
        reasons.append("code")

    if needs_verification:
        score += 1
        reasons.append("verification")

    if explicit_planning:
        score += 2
        reasons.append("planning")

    if multi_step:
        score += 2
        reasons.append("multi_step")

    if len(original) >= 500:
        score += 1
        reasons.append("long_request")

    conjunction_count = len(
        re.findall(
            r"\b(e|depois|tamb[eé]m|then|and|also)\b",
            text,
        )
    )

    if conjunction_count >= 4:
        score += 1
        reasons.append("compound_request")

    needs_tools = any(
        (
            needs_research,
            needs_calculation,
            needs_code,
        )
    )

    needs_planning = (
        explicit_planning
        or multi_step
        or score >= 3
    )

    if score >= 5:
        complexity = "complex"
    elif score >= 2:
        complexity = "moderate"
    else:
        complexity = "simple"

    return TaskAnalysis(
        query=original,
        complexity=complexity,
        needs_planning=needs_planning,
        needs_research=needs_research,
        needs_tools=needs_tools,
        needs_calculation=needs_calculation,
        needs_code=needs_code,
        needs_verification=needs_verification,
        multi_step=multi_step,
        score=score,
        reasons=tuple(reasons),
    )
