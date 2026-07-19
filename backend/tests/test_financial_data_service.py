import pytest

from app.providers.ticker import normalize_indian_ticker
from app.utils.exceptions import TickerNotFoundError


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("INFY", "INFY.NS"),
        ("infy", "INFY.NS"),
        ("RELIANCE", "RELIANCE.NS"),
        ("INFY.NS", "INFY.NS"),
        ("INFY.BO", "INFY.BO"),
        ("TCS.NS", "TCS.NS"),
        (" HDFCBANK ", "HDFCBANK.NS"),
    ],
)
def test_normalize_indian_ticker(raw: str, expected: str) -> None:
    assert normalize_indian_ticker(raw) == expected


@pytest.mark.asyncio
async def test_collect_returns_structured_financial_data(financial_data_service) -> None:
    result = await financial_data_service.collect("infy")

    assert result.ticker == "INFY.NS"
    assert result.profile.company_name == "Infosys Limited"
    assert result.profile.sector == "Technology"
    assert len(result.income_statements) == 1
    assert len(result.balance_sheets) == 1
    assert len(result.ratios) == 1
    assert len(result.key_metrics) == 1
    assert result.market_data is not None
    assert result.market_data.current_price == 1500.0
    assert "yahoo_finance" in result.data_sources
    assert result.warnings == []


@pytest.mark.asyncio
async def test_collect_continues_when_market_data_fails(financial_data_service, mock_provider) -> None:
    mock_provider.get_market_data.side_effect = TickerNotFoundError("Market data unavailable")

    result = await financial_data_service.collect("INFY")

    assert result.market_data is None
    assert len(result.warnings) == 1
    assert result.warnings[0].source == "yahoo_finance"
    assert "yahoo_finance" in result.data_sources


@pytest.mark.asyncio
async def test_collect_raises_when_profile_missing(financial_data_service, mock_provider) -> None:
    mock_provider.get_company_profile.side_effect = TickerNotFoundError("No profile")

    with pytest.raises(TickerNotFoundError):
        await financial_data_service.collect("INVALID")


@pytest.mark.asyncio
async def test_collect_warns_when_statements_missing(financial_data_service, mock_provider) -> None:
    mock_provider.get_income_statement.return_value = []
    mock_provider.get_balance_sheet.return_value = []

    result = await financial_data_service.collect("INFY")

    assert result.income_statements == []
    assert result.balance_sheets == []
    assert any("Income statement" in warning.message for warning in result.warnings)
    assert any("Balance sheet" in warning.message for warning in result.warnings)


@pytest.mark.asyncio
async def test_get_summary_returns_compact_response(financial_data_service) -> None:
    summary = await financial_data_service.get_summary("INFY")

    assert summary.ticker == "INFY.NS"
    assert summary.company_name == "Infosys Limited"
    assert summary.currency == "INR"
    assert summary.current_price == 1500.0
    assert summary.pe_ratio == 25.5
    assert summary.data_source == "yahoo"
    assert summary.fundamentals_source == "yahoo"
