"""Indian equity ticker normalization for Yahoo Finance (NSE / BSE)."""

import re

# Common NSE tickers referenced in the MVP – normalization applies to all symbols.
_INDIAN_EXCHANGE_SUFFIXES = (".NS", ".BO")
_TICKER_PATTERN = re.compile(r"^[A-Z0-9&.-]+$")


def normalize_indian_ticker(ticker: str) -> str:
    """
    Normalize a user-supplied ticker for Yahoo Finance Indian equities.

    Examples:
        INFY       -> INFY.NS
        RELIANCE   -> RELIANCE.NS
        INFY.NS    -> INFY.NS  (unchanged)
        INFY.BO    -> INFY.BO  (unchanged)
    """
    cleaned = ticker.strip().upper()
    if not cleaned:
        return cleaned

    for suffix in _INDIAN_EXCHANGE_SUFFIXES:
        if cleaned.endswith(suffix):
            return cleaned

    return f"{cleaned}.NS"


def validate_ticker_format(ticker: str) -> None:
    """Raise ValueError when the ticker format is clearly invalid."""
    if not ticker:
        raise ValueError("Ticker symbol is required")
    if not _TICKER_PATTERN.match(ticker):
        raise ValueError(f"Invalid ticker format: {ticker}")
