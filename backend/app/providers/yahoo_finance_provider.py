"""
Yahoo Finance provider – primary data source for Indian equities (via yfinance).

Agents and routes must not import yfinance directly; they go through
FinancialDataService -> YahooFinanceProvider.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import yfinance as yf

from app.schemas.financial import (
    BalanceSheet,
    CashFlowStatement,
    CompanyProfile,
    FinancialRatios,
    HistoricalPricePoint,
    IncomeStatement,
    KeyMetrics,
    MarketData,
)
from app.utils.exceptions import ExternalServiceError, TickerNotFoundError
from app.utils.logging import get_logger

logger = get_logger(__name__)

DATA_SOURCE_LABEL = "Yahoo Finance"


def _series_value(series: Any, *keys: str) -> float | None:
    for key in keys:
        if key in series.index:
            value = series[key]
            if value is not None and value == value:  # NaN check
                return float(value)
    return None


def _format_column_date(column: Any) -> str:
    if hasattr(column, "strftime"):
        return column.strftime("%Y-%m-%d")
    return str(column)


def _is_empty_info(info: dict[str, Any]) -> bool:
    if not info:
        return True
    has_price = info.get("regularMarketPrice") is not None or info.get("currentPrice") is not None
    has_name = bool(info.get("shortName") or info.get("longName") or info.get("symbol"))
    return not has_price and not has_name


def _fetch_ticker_sync(ticker: str) -> yf.Ticker:
    return yf.Ticker(ticker)


def _search_companies_sync(query: str, limit: int) -> list[dict[str, Any]]:
    """Search Indian equities on Yahoo Finance via yfinance Search."""
    try:
        from yfinance import Search
    except ImportError as exc:
        raise ExternalServiceError("yfinance Search is not available") from exc

    search = Search(query, max_results=max(limit * 3, 15))
    quotes = getattr(search, "quotes", None) or []
    results: list[dict[str, Any]] = []

    for quote in quotes:
        if not isinstance(quote, dict):
            continue
        raw_symbol = str(quote.get("symbol") or "").upper()
        if raw_symbol.endswith(".NS"):
            exchange = "NSE"
            symbol = raw_symbol[:-3]
        elif raw_symbol.endswith(".BO"):
            exchange = "BSE"
            symbol = raw_symbol[:-3]
        else:
            continue

        company_name = (
            quote.get("longname")
            or quote.get("shortname")
            or quote.get("name")
            or symbol
        )
        results.append(
            {
                "symbol": symbol,
                "exchange": exchange,
                "company_name": str(company_name),
                "sector": quote.get("sector") or quote.get("industry"),
            }
        )
        if len(results) >= limit:
            break

    return results


def _fetch_info_sync(ticker: str) -> dict[str, Any]:
    stock = _fetch_ticker_sync(ticker)
    info = stock.info or {}
    if _is_empty_info(info):
        raise TickerNotFoundError(f"No Yahoo Finance data found for ticker: {ticker}")
    return info


def _map_profile(ticker: str, info: dict[str, Any]) -> CompanyProfile:
    return CompanyProfile(
        symbol=info.get("symbol") or ticker,
        company_name=info.get("longName") or info.get("shortName") or "",
        exchange=info.get("exchange"),
        sector=info.get("sector"),
        industry=info.get("industry"),
        country=info.get("country"),
        currency=info.get("currency") or "INR",
        market_cap=info.get("marketCap"),
        price=info.get("regularMarketPrice") or info.get("currentPrice"),
        beta=info.get("beta"),
        description=info.get("longBusinessSummary"),
        ceo=None,
        website=info.get("website"),
        ipo_date=None,
    )


def _map_income_statements(stock: yf.Ticker) -> list[IncomeStatement]:
    df = stock.income_stmt
    if df is None or df.empty:
        df = stock.financials
    if df is None or df.empty:
        return []

    statements: list[IncomeStatement] = []
    for column in df.columns:
        series = df[column]
        statements.append(
            IncomeStatement(
                date=_format_column_date(column),
                period="FY",
                revenue=_series_value(series, "Total Revenue", "TotalRevenue"),
                gross_profit=_series_value(series, "Gross Profit", "GrossProfit"),
                operating_income=_series_value(series, "Operating Income", "OperatingIncome"),
                net_income=_series_value(series, "Net Income", "NetIncome"),
                eps=_series_value(series, "Basic EPS", "Diluted EPS"),
                ebitda=_series_value(series, "EBITDA", "Normalized EBITDA"),
            )
        )
    return statements


def _map_balance_sheets(stock: yf.Ticker) -> list[BalanceSheet]:
    df = stock.balance_sheet
    if df is None or df.empty:
        return []

    sheets: list[BalanceSheet] = []
    for column in df.columns:
        series = df[column]
        sheets.append(
            BalanceSheet(
                date=_format_column_date(column),
                period="FY",
                total_assets=_series_value(series, "Total Assets", "TotalAssets"),
                total_liabilities=_series_value(
                    series, "Total Liabilities Net Minority Interest", "Total Liab"
                ),
                total_equity=_series_value(
                    series,
                    "Stockholders Equity",
                    "Total Equity Gross Minority Interest",
                    "Common Stock Equity",
                ),
                total_debt=_series_value(series, "Total Debt", "Net Debt"),
                cash_and_equivalents=_series_value(
                    series, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"
                ),
            )
        )
    return sheets


def _map_cash_flow_statements(stock: yf.Ticker) -> list[CashFlowStatement]:
    df = stock.cashflow
    if df is None or df.empty:
        df = stock.cash_flow
    if df is None or df.empty:
        return []

    statements: list[CashFlowStatement] = []
    for column in df.columns:
        series = df[column]
        statements.append(
            CashFlowStatement(
                date=_format_column_date(column),
                period="FY",
                operating_cash_flow=_series_value(
                    series, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities"
                ),
                investing_cash_flow=_series_value(
                    series, "Investing Cash Flow", "Cash Flow From Continuing Investing Activities"
                ),
                financing_cash_flow=_series_value(
                    series, "Financing Cash Flow", "Cash Flow From Continuing Financing Activities"
                ),
                free_cash_flow=_series_value(series, "Free Cash Flow"),
                capital_expenditure=_series_value(series, "Capital Expenditure"),
            )
        )
    return statements


def _map_ratios_from_info(info: dict[str, Any]) -> list[FinancialRatios]:
    if _is_empty_info(info):
        return []

    return [
        FinancialRatios(
            date=datetime.now(UTC).strftime("%Y-%m-%d"),
            period="TTM",
            current_ratio=info.get("currentRatio"),
            debt_to_equity=info.get("debtToEquity"),
            return_on_equity=info.get("returnOnEquity"),
            return_on_assets=info.get("returnOnAssets"),
            gross_profit_margin=info.get("grossMargins"),
            net_profit_margin=info.get("profitMargins"),
            price_to_earnings=info.get("trailingPE"),
            price_to_book=info.get("priceToBook"),
        )
    ]


def _map_key_metrics_from_info(info: dict[str, Any]) -> list[KeyMetrics]:
    if _is_empty_info(info):
        return []

    return [
        KeyMetrics(
            date=datetime.now(UTC).strftime("%Y-%m-%d"),
            period="TTM",
            revenue_per_share=info.get("revenuePerShare"),
            net_income_per_share=info.get("trailingEps"),
            enterprise_value=info.get("enterpriseValue"),
            ev_to_ebitda=info.get("enterpriseToEbitda"),
            pe_ratio=info.get("trailingPE"),
            pb_ratio=info.get("priceToBook"),
        )
    ]


def _map_market_data(info: dict[str, Any]) -> MarketData:
    return MarketData(
        current_price=info.get("regularMarketPrice") or info.get("currentPrice"),
        previous_close=info.get("previousClose") or info.get("regularMarketPreviousClose"),
        day_high=info.get("dayHigh") or info.get("regularMarketDayHigh"),
        day_low=info.get("dayLow") or info.get("regularMarketDayLow"),
        fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
        fifty_two_week_low=info.get("fiftyTwoWeekLow"),
        volume=info.get("volume") or info.get("regularMarketVolume"),
        average_volume=info.get("averageVolume") or info.get("averageDailyVolume10Day"),
        currency=info.get("currency") or "INR",
    )


def _map_historical_prices_sync(ticker: str, period: str) -> list[HistoricalPricePoint]:
    stock = _fetch_ticker_sync(ticker)
    history = stock.history(period=period)
    if history is None or history.empty:
        return []

    return _dataframe_to_points(history)


def _map_historical_candles_sync(
    ticker: str,
    *,
    interval: str = "1d",
    start: str | None = None,
    end: str | None = None,
    period: str | None = None,
) -> list[HistoricalPricePoint]:
    stock = _fetch_ticker_sync(ticker)
    kwargs: dict[str, str] = {"interval": interval}
    if start:
        kwargs["start"] = start
    if end:
        kwargs["end"] = end
    if period and not start:
        kwargs["period"] = period

    history = stock.history(**kwargs)
    if history is None or history.empty:
        return []

    return _dataframe_to_points(history)


def _dataframe_to_points(history) -> list[HistoricalPricePoint]:
    points: list[HistoricalPricePoint] = []
    for index, row in history.iterrows():
        date_str = index.strftime("%Y-%m-%d") if hasattr(index, "strftime") else str(index)
        if hasattr(index, "hour"):
            date_str = index.strftime("%Y-%m-%dT%H:%M:%S")
        points.append(
            HistoricalPricePoint(
                date=date_str,
                open=float(row["Open"]) if row.get("Open") == row.get("Open") else None,
                high=float(row["High"]) if row.get("High") == row.get("High") else None,
                low=float(row["Low"]) if row.get("Low") == row.get("Low") else None,
                close=float(row["Close"]) if row.get("Close") == row.get("Close") else None,
                volume=int(row["Volume"]) if row.get("Volume") == row.get("Volume") else None,
            )
        )
    return points


class YahooFinanceProvider:
    """Yahoo Finance implementation of FinancialDataProvider."""

    name = "yahoo_finance"

    async def _call(self, method: str, ticker: str, fn, *args):
        logger.info("YahooFinanceProvider.%s ticker=%s", method, ticker)
        try:
            return await asyncio.to_thread(fn, ticker, *args)
        except TickerNotFoundError:
            logger.warning("YahooFinanceProvider.%s ticker not found: %s", method, ticker)
            raise
        except Exception as exc:
            logger.error("YahooFinanceProvider.%s failed for %s: %s", method, ticker, exc)
            raise ExternalServiceError(
                f"Yahoo Finance request failed during {method} for {ticker}"
            ) from exc

    async def get_company_profile(self, ticker: str) -> CompanyProfile:
        info = await self._call("get_company_profile", ticker, _fetch_info_sync)
        return _map_profile(ticker, info)

    async def get_current_price(self, ticker: str) -> float | None:
        info = await self._call("get_current_price", ticker, _fetch_info_sync)
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        return float(price) if price is not None else None

    async def get_income_statement(self, ticker: str) -> list[IncomeStatement]:
        def _fetch(symbol: str) -> list[IncomeStatement]:
            stock = _fetch_ticker_sync(symbol)
            _fetch_info_sync(symbol)  # validate ticker exists
            return _map_income_statements(stock)

        return await self._call("get_income_statement", ticker, _fetch)

    async def get_balance_sheet(self, ticker: str) -> list[BalanceSheet]:
        def _fetch(symbol: str) -> list[BalanceSheet]:
            stock = _fetch_ticker_sync(symbol)
            _fetch_info_sync(symbol)
            return _map_balance_sheets(stock)

        return await self._call("get_balance_sheet", ticker, _fetch)

    async def get_cash_flow(self, ticker: str) -> list[CashFlowStatement]:
        def _fetch(symbol: str) -> list[CashFlowStatement]:
            stock = _fetch_ticker_sync(symbol)
            _fetch_info_sync(symbol)
            return _map_cash_flow_statements(stock)

        return await self._call("get_cash_flow", ticker, _fetch)

    async def get_financial_ratios(self, ticker: str) -> list[FinancialRatios]:
        info = await self._call("get_financial_ratios", ticker, _fetch_info_sync)
        return _map_ratios_from_info(info)

    async def get_key_metrics(self, ticker: str) -> list[KeyMetrics]:
        info = await self._call("get_key_metrics", ticker, _fetch_info_sync)
        return _map_key_metrics_from_info(info)

    async def get_market_data(self, ticker: str) -> MarketData:
        info = await self._call("get_market_data", ticker, _fetch_info_sync)
        return _map_market_data(info)

    async def get_historical_prices(
        self, ticker: str, period: str = "5y"
    ) -> list[HistoricalPricePoint]:
        def _fetch(symbol: str, hist_period: str) -> list[HistoricalPricePoint]:
            _fetch_info_sync(symbol)
            return _map_historical_prices_sync(symbol, hist_period)

        return await self._call("get_historical_prices", ticker, _fetch, period)

    async def get_historical_candles(
        self,
        ticker: str,
        *,
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
        period: str | None = None,
    ) -> list[HistoricalPricePoint]:
        def _fetch(
            symbol: str,
            yf_interval: str,
            start_date: str | None,
            end_date: str | None,
            hist_period: str | None,
        ) -> list[HistoricalPricePoint]:
            return _map_historical_candles_sync(
                symbol,
                interval=yf_interval,
                start=start_date,
                end=end_date,
                period=hist_period,
            )

        return await self._call(
            "get_historical_candles",
            ticker,
            _fetch,
            interval,
            start,
            end,
            period,
        )

    async def get_supplemental_metrics(self, ticker: str) -> dict[str, float | None]:
        info = await self._call("get_supplemental_metrics", ticker, _fetch_info_sync)
        return {
            "revenue_growth": info.get("revenueGrowth"),
            "dividend_yield": info.get("dividendYield"),
        }

    async def search_companies(self, query: str, *, limit: int = 12) -> list[dict[str, Any]]:
        return await self._call("search_companies", query, _search_companies_sync, limit)
