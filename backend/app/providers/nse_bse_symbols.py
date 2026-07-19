"""Symbol helpers for NSE/BSE MCP tools."""

from app.providers.ticker import normalize_indian_ticker


def resolve_exchange_symbol(ticker: str) -> tuple[str, str]:
    """
    Return (bare_symbol, exchange) for an Indian equity ticker.

    Examples:
        INFY -> (INFY, NSE)
        INFY.NS -> (INFY, NSE)
        RELIANCE.BO -> (RELIANCE, BSE)
    """
    normalized = normalize_indian_ticker(ticker)
    if normalized.endswith(".BO"):
        return normalized[:-3], "BSE"
    if normalized.endswith(".NS"):
        return normalized[:-3], "NSE"
    return normalized, "NSE"
