"""Guardrail check – unsupported conclusions and analysis quality."""

import re

from app.guardrails.evidence import EvidenceCorpus
from app.schemas.financial import FinancialResearchResponse
from app.schemas.research import GuardrailIssue

PREMATURE_RECOMMENDATION_PATTERNS = [
    r"\bstrong buy\b",
    r"\bwe recommend (?:buying|selling)\b",
    r"\b(?:buy|sell|avoid) (?:the stock|this stock|now)\b",
    r"\brating:\s*(?:buy|sell|avoid)\b",
    r"\bfinal recommendation\b",
]

UNSUPPORTED_CERTAINTY_PATTERNS = [
    r"\bguaranteed\b",
    r"\bwill definitely\b",
    r"\bno risk\b",
    r"\bcannot lose\b",
    r"\bcertain to outperform\b",
    r"\b100% certainty\b",
]

CONTRADICTION_PATTERNS = [
    (r"\bdeclining revenue\b", "revenue_growth"),
    (r"\brevenue (?:is|are) (?:falling|decreasing|shrinking)\b", "revenue_growth"),
    (r"\bgrowing revenue\b", "revenue_decline"),
    (r"\brevenue (?:is|are) (?:growing|increasing|rising)\b", "revenue_decline"),
]

MIN_ANALYSIS_LENGTH = 100


def check_analysis_quality(ticker: str, analysis: str | None) -> list[GuardrailIssue]:
    issues: list[GuardrailIssue] = []

    if not analysis or len(analysis.strip()) < MIN_ANALYSIS_LENGTH:
        issues.append(
            GuardrailIssue(
                code="insufficient_analysis",
                message="Analyst thesis is missing or too short",
                severity="error",
            )
        )
        return issues

    if ticker.upper() not in analysis.upper():
        issues.append(
            GuardrailIssue(
                code="ticker_not_in_analysis",
                message=f"Analysis does not reference ticker {ticker}",
                severity="warning",
            )
        )

    # Required sections heuristic
    section_keywords = ["risk", "growth", "profitab", "valuation", "cash flow", "debt"]
    found = sum(1 for kw in section_keywords if kw in analysis.lower())
    if found < 2:
        issues.append(
            GuardrailIssue(
                code="incomplete_analysis_sections",
                message="Analysis lacks coverage of key thesis sections (growth, risks, valuation, etc.)",
                severity="warning",
            )
        )

    return issues


def check_unsupported_conclusions(
    analysis: str,
    corpus: EvidenceCorpus,
    financial_data: FinancialResearchResponse | None,
) -> list[GuardrailIssue]:
    issues: list[GuardrailIssue] = []
    lower = analysis.lower()

    for pattern in PREMATURE_RECOMMENDATION_PATTERNS:
        if re.search(pattern, lower):
            issues.append(
                GuardrailIssue(
                    code="premature_recommendation",
                    message=(
                        "Analysis contains a buy/sell recommendation – "
                        "only Agent 4 should issue ratings"
                    ),
                    severity="error",
                )
            )
            break

    for pattern in UNSUPPORTED_CERTAINTY_PATTERNS:
        if re.search(pattern, lower):
            issues.append(
                GuardrailIssue(
                    code="unsupported_certainty",
                    message="Analysis uses unsupported certainty language",
                    severity="warning",
                )
            )
            break

    if financial_data and financial_data.income_statements:
        issues.extend(_check_revenue_contradictions(analysis, financial_data))

    return issues


def _check_revenue_contradictions(
    analysis: str,
    financial_data: FinancialResearchResponse,
) -> list[GuardrailIssue]:
    issues: list[GuardrailIssue] = []
    statements = [
        s for s in financial_data.income_statements if s.revenue is not None and s.date
    ]
    if len(statements) < 2:
        return issues

    ordered = sorted(statements, key=lambda s: s.date)
    revenues = [s.revenue for s in ordered if s.revenue is not None]
    if len(revenues) < 2:
        return issues

    growing = revenues[-1] > revenues[-2]
    declining = revenues[-1] < revenues[-2]
    lower = analysis.lower()

    if growing and re.search(CONTRADICTION_PATTERNS[0][0], lower):
        issues.append(
            GuardrailIssue(
                code="contradictory_revenue_claim",
                message="Analysis claims declining revenue but statements show revenue growth",
                severity="error",
            )
        )
    elif declining and re.search(CONTRADICTION_PATTERNS[2][0], lower):
        issues.append(
            GuardrailIssue(
                code="contradictory_revenue_claim",
                message="Analysis claims growing revenue but statements show revenue decline",
                severity="error",
            )
        )

    return issues
