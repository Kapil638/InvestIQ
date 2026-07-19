"""
Guardrail engine – orchestrates all validation checks before Agent 4.

Checks run in order:
  1. Completeness – missing data
  2. Staleness – outdated financials and news
  3. Hallucinations – unsupported numeric claims
  4. Conclusions – premature recommendations, contradictions
  5. Analysis quality – length, ticker reference, section coverage
"""

from app.core.config import Settings, get_settings
from app.guardrails.checks.completeness import check_completeness
from app.guardrails.checks.conclusions import check_analysis_quality, check_unsupported_conclusions
from app.guardrails.checks.hallucination import check_hallucinations
from app.guardrails.checks.staleness import check_staleness
from app.guardrails.evidence import EvidenceCorpus, build_evidence_corpus
from app.schemas.financial import FinancialResearchResponse
from app.schemas.news import NewsResearchResponse
from app.schemas.research import GuardrailIssue, GuardrailResult

# Issues that can be fixed by re-running Agent 3 with feedback
RETRYABLE_CODES = frozenset(
    {
        "insufficient_analysis",
        "ticker_not_in_analysis",
        "incomplete_analysis_sections",
        "unsupported_numeric_claims",
        "premature_recommendation",
        "contradictory_revenue_claim",
        "unsupported_certainty",
        "company_name_mismatch",
    }
)

# Data collection failures cannot be fixed by re-analysis
NON_RETRYABLE_CODES = frozenset(
    {
        "missing_financial_data",
        "missing_news_data",
        "incomplete_profile",
        "stale_financial_statements",
    }
)


class GuardrailEngine:
    """Runs all guardrail checks and determines if Agent 4 may proceed."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def validate(
        self,
        ticker: str,
        financial_data: FinancialResearchResponse | None,
        news_data: NewsResearchResponse | None,
        analysis: str | None,
        *,
        corpus: EvidenceCorpus | None = None,
    ) -> GuardrailResult:
        issues: list[GuardrailIssue] = []
        if corpus is None:
            corpus = build_evidence_corpus(ticker, financial_data, news_data)

        issues.extend(check_completeness(financial_data, news_data))

        if financial_data is not None or news_data is not None:
            issues.extend(
                check_staleness(
                    financial_data,
                    news_data,
                    corpus,
                    collection_max_age_hours=self._settings.guardrail_collection_max_age_hours,
                    statement_max_age_months=self._settings.guardrail_statement_max_age_months,
                    news_max_age_days=self._settings.guardrail_news_max_age_days,
                )
            )

        if analysis:
            issues.extend(check_hallucinations(analysis, corpus))
            issues.extend(check_unsupported_conclusions(analysis, corpus, financial_data))

        issues.extend(check_analysis_quality(ticker, analysis))

        passed = self._determine_pass(issues)
        blocked_reason = _blocked_reason(issues) if not passed else None

        return GuardrailResult(
            passed=passed,
            issues=_deduplicate_issues(issues),
            blocked_reason=blocked_reason,
        )

    def _determine_pass(self, issues: list[GuardrailIssue]) -> bool:
        has_errors = any(issue.severity == "error" for issue in issues)
        if has_errors:
            return False
        if self._settings.guardrail_block_on_warnings:
            return not any(issue.severity == "warning" for issue in issues)
        return True

    @staticmethod
    def is_retryable(result: GuardrailResult) -> bool:
        if result.passed:
            return False
        codes = {issue.code for issue in result.issues}
        if codes & NON_RETRYABLE_CODES:
            return False
        return bool(codes & RETRYABLE_CODES)

    @staticmethod
    def format_feedback(issues: list[GuardrailIssue]) -> str:
        lines = [
            "GUARDRAIL FEEDBACK – revise your analysis to address these issues:",
        ]
        for issue in issues:
            lines.append(f"- [{issue.severity.upper()}] {issue.code}: {issue.message}")
        lines.append(
            "Only cite numbers present in the source data. "
            "Do not issue buy/sell ratings – that is Agent 4's job."
        )
        return "\n".join(lines)



def _blocked_reason(issues: list[GuardrailIssue]) -> str | None:
    errors = [i for i in issues if i.severity == "error"]
    if not errors:
        return None
    return "; ".join(f"{e.code}: {e.message}" for e in errors[:3])


def _deduplicate_issues(issues: list[GuardrailIssue]) -> list[GuardrailIssue]:
    seen: set[str] = set()
    unique: list[GuardrailIssue] = []
    for issue in issues:
        key = f"{issue.code}:{issue.message}"
        if key not in seen:
            seen.add(key)
            unique.append(issue)
    return unique


def validate_before_recommendation(
    ticker: str,
    financial_data: FinancialResearchResponse | None,
    news_data: NewsResearchResponse | None,
    analysis: str | None,
    settings: Settings | None = None,
) -> GuardrailResult:
    """Backward-compatible entry point used by the research pipeline."""
    from app.core.config import get_settings

    engine = GuardrailEngine(settings or get_settings())
    return engine.validate(ticker, financial_data, news_data, analysis)
