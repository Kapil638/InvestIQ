"""Kite symbol helpers for NSE/BSE instruments."""

import re

_KITE_SYMBOL_PATTERN = re.compile(r"^(NSE|BSE|NFO|BFO|CDS|MCX):[A-Z0-9&.-]+$")


def to_kite_symbol(ticker: str, exchange: str = "NSE") -> str:
    """
    Convert InvestIQ/Yahoo ticker to Kite instrument key.

    Examples:
        INFY -> NSE:INFY
        INFY.NS -> NSE:INFY
        RELIANCE.BO -> BSE:RELIANCE
        NSE:TCS -> NSE:TCS
    """
    cleaned = ticker.strip().upper()
    if not cleaned:
        return cleaned

    if ":" in cleaned and _KITE_SYMBOL_PATTERN.match(cleaned):
        return cleaned

    if cleaned.endswith(".NS"):
        return f"NSE:{cleaned[:-3]}"
    if cleaned.endswith(".BO"):
        return f"BSE:{cleaned[:-3]}"

    return f"{exchange.upper()}:{cleaned}"


def from_kite_symbol(kite_symbol: str) -> str:
    """Return bare NSE-style symbol for display (INFY from NSE:INFY)."""
    if ":" in kite_symbol:
        return kite_symbol.split(":", 1)[1]
    return kite_symbol
