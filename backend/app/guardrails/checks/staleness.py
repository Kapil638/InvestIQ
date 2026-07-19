"""Guardrail check – stale financial data and outdated news."""

from datetime import UTC, datetime, timedelta

from app.guardrails.evidence import EvidenceCorpus
from app.schemas.financial import FinancialResearchResponse
from app.schemas.news import NewsResearchResponse
from app.schemas.research import GuardrailIssue


def check_staleness(
    financial_data: FinancialResearchResponse | None,
    news_data: NewsResearchResponse | None,
    corpus: EvidenceCorpus,
    *,
    collection_max_age_hours: int = 24,
    statement_max_age_months: int = 18,
    news_max_age_days: int = 30,
) -> list[GuardrailIssue]:
    issues: list[GuardrailIssue] = []

    if financial_data:
        _check_collection_age(
            financial_data.collected_at,
            "financial_data",
            collection_max_age_hours,
            issues,
        )
        _check_statement_dates(corpus.statement_dates, statement_max_age_months, issues)

    if news_data:
        _check_collection_age(
            news_data.collected_at,
            "news_data",
            collection_max_age_hours,
            issues,
        )
        _check_news_dates(corpus.news_dates, news_max_age_days, issues)

    return issues


def _check_collection_age(
    collected_at: datetime,
    label: str,
    max_age_hours: int,
    issues: list[GuardrailIssue],
) -> None:
    now = datetime.now(UTC)
    ts = collected_at if collected_at.tzinfo else collected_at.replace(tzinfo=UTC)
    if now - ts > timedelta(hours=max_age_hours):
        issues.append(
            GuardrailIssue(
                code=f"stale_{label}",
                message=f"{label} collection is older than {max_age_hours} hours",
                severity="warning",
            )
        )


def _check_statement_dates(
    dates: list[str],
    max_age_months: int,
    issues: list[GuardrailIssue],
) -> None:
    if not dates:
        return

    parsed = [_parse_date(d) for d in dates]
    parsed = [d for d in parsed if d is not None]
    if not parsed:
        issues.append(
            GuardrailIssue(
                code="unparseable_statement_dates",
                message="Financial statement dates could not be parsed",
                severity="warning",
            )
        )
        return

    latest = max(parsed)
    cutoff = datetime.now(UTC) - timedelta(days=max_age_months * 30)
    if latest < cutoff:
        issues.append(
            GuardrailIssue(
                code="stale_financial_statements",
                message=(
                    f"Latest financial statement ({latest.date()}) is older than "
                    f"{max_age_months} months"
                ),
                severity="error",
            )
        )


def _check_news_dates(
    dates: list[str],
    max_age_days: int,
    issues: list[GuardrailIssue],
) -> None:
    if not dates:
        issues.append(
            GuardrailIssue(
                code="undated_news",
                message="News articles have no published dates – freshness cannot be verified",
                severity="warning",
            )
        )
        return

    parsed = [_parse_date(d) for d in dates]
    parsed = [d for d in parsed if d is not None]
    if not parsed:
        issues.append(
            GuardrailIssue(
                code="unparseable_news_dates",
                message="News published dates could not be parsed",
                severity="warning",
            )
        )
        return

    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    recent = [d for d in parsed if d >= cutoff]
    if not recent:
        issues.append(
            GuardrailIssue(
                code="outdated_news",
                message=f"All news articles are older than {max_age_days} days",
                severity="warning",
            )
        )


def _parse_date(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(value[:19], fmt)
            return dt.replace(tzinfo=UTC)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None
