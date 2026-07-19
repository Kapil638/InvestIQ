"""Evidence corpus built from Agent 1 & 2 structured outputs for guardrail checks."""

from dataclasses import dataclass, field

from app.schemas.financial import FinancialResearchResponse
from app.schemas.news import NewsArticle, NewsResearchResponse


@dataclass
class EvidenceCorpus:
    """Normalized facts extracted from source data – used to verify analysis claims."""

    ticker: str
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    keywords: set[str] = field(default_factory=set)
    numbers: set[float] = field(default_factory=set)
    statement_dates: list[str] = field(default_factory=list)
    news_dates: list[str] = field(default_factory=list)
    source_text: str = ""


def build_evidence_corpus(
    ticker: str,
    financial_data: FinancialResearchResponse | None,
    news_data: NewsResearchResponse | None,
) -> EvidenceCorpus:
    corpus = EvidenceCorpus(ticker=ticker.upper())
    text_parts: list[str] = [ticker.upper()]

    if financial_data:
        profile = financial_data.profile
        corpus.company_name = profile.company_name
        corpus.sector = profile.sector
        corpus.industry = profile.industry

        for value in (
            profile.company_name,
            profile.sector,
            profile.industry,
            profile.ceo,
            profile.exchange,
        ):
            _add_keywords(corpus, value)

        for field_name in ("market_cap", "price", "beta"):
            val = getattr(profile, field_name, None)
            if val is not None:
                corpus.numbers.add(float(val))
                text_parts.append(str(val))

        for statement in financial_data.income_statements:
            corpus.statement_dates.append(statement.date)
            text_parts.append(statement.date)
            for val in (statement.revenue, statement.net_income, statement.eps, statement.ebitda):
                if val is not None:
                    corpus.numbers.add(float(val))
                    text_parts.append(str(val))

        for sheet in financial_data.balance_sheets:
            corpus.statement_dates.append(sheet.date)
            for val in (sheet.total_assets, sheet.total_debt, sheet.total_equity):
                if val is not None:
                    corpus.numbers.add(float(val))

        for ratio in financial_data.ratios:
            for val in (
                ratio.return_on_equity,
                ratio.net_profit_margin,
                ratio.debt_to_equity,
                ratio.price_to_earnings,
            ):
                if val is not None:
                    corpus.numbers.add(float(val))
                    if 0 < abs(val) <= 1:
                        corpus.numbers.add(round(float(val) * 100, 2))

        if financial_data.market_data:
            md = financial_data.market_data
            for val in (md.current_price, md.fifty_two_week_high, md.fifty_two_week_low):
                if val is not None:
                    corpus.numbers.add(float(val))

    if news_data:
        all_articles = (
            news_data.latest_news + news_data.earnings_and_filings + news_data.sector_news
        )
        for article in all_articles:
            _add_article_evidence(corpus, text_parts, article)

    corpus.source_text = " ".join(text_parts).lower()
    return corpus


def _add_article_evidence(
    corpus: EvidenceCorpus, text_parts: list[str], article: NewsArticle
) -> None:
    if article.published_date:
        corpus.news_dates.append(article.published_date)
        text_parts.append(article.published_date)
    for value in (article.title, article.snippet, article.source):
        _add_keywords(corpus, value)
        if value:
            text_parts.append(value)


def _add_keywords(corpus: EvidenceCorpus, value: str | None) -> None:
    if not value:
        return
    corpus.keywords.add(value.lower())
    for token in value.lower().split():
        if len(token) > 3:
            corpus.keywords.add(token)
