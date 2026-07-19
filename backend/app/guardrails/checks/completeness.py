"""Guardrail check – data completeness."""

from app.schemas.financial import FinancialResearchResponse
from app.schemas.news import NewsResearchResponse
from app.schemas.research import GuardrailIssue


def check_completeness(
    financial_data: FinancialResearchResponse | None,
    news_data: NewsResearchResponse | None,
) -> list[GuardrailIssue]:
    issues: list[GuardrailIssue] = []

    if financial_data is None:
        issues.append(
            GuardrailIssue(
                code="missing_financial_data",
                message="Financial data is missing",
                severity="error",
            )
        )
        return issues

    if not financial_data.profile.company_name:
        issues.append(
            GuardrailIssue(
                code="incomplete_profile",
                message="Company profile is incomplete – missing company name",
                severity="error",
            )
        )

    if not financial_data.income_statements:
        issues.append(
            GuardrailIssue(
                code="missing_income_statements",
                message="Income statements are missing",
                severity="warning",
            )
        )

    if not financial_data.balance_sheets:
        issues.append(
            GuardrailIssue(
                code="missing_balance_sheets",
                message="Balance sheets are missing",
                severity="warning",
            )
        )

    if financial_data.warnings:
        for warning in financial_data.warnings:
            issues.append(
                GuardrailIssue(
                    code="financial_collection_warning",
                    message=f"{warning.source}: {warning.message}",
                    severity="warning",
                )
            )

    if news_data is None:
        issues.append(
            GuardrailIssue(
                code="missing_news_data",
                message="News research data is missing",
                severity="error",
            )
        )
        return issues

    total_articles = (
        len(news_data.latest_news)
        + len(news_data.earnings_and_filings)
        + len(news_data.sector_news)
    )
    if total_articles == 0:
        issues.append(
            GuardrailIssue(
                code="no_news_articles",
                message="No news articles were collected",
                severity="warning",
            )
        )

    if news_data.warnings:
        for warning in news_data.warnings:
            issues.append(
                GuardrailIssue(
                    code="news_collection_warning",
                    message=warning,
                    severity="warning",
                )
            )

    return issues
