"""Map chart timeframes and candle intervals for historical price data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

VALID_INTERVALS = frozenset({"minute", "5minute", "15minute", "day", "week", "month"})

TIMEFRAME_LABELS = ("1D", "5D", "1M", "3M", "6M", "1Y", "3Y", "5Y")


def validate_interval(interval: str) -> str:
    normalized = interval.strip().lower()
    if normalized not in VALID_INTERVALS:
        raise ValueError(
            f"Invalid interval '{interval}'. "
            f"Allowed: {', '.join(sorted(VALID_INTERVALS))}"
        )
    return normalized


def resolve_timeframe(timeframe: str, *, now: datetime | None = None) -> tuple[str, str, str]:
    """
    Map a UI timeframe label to (interval, from_date, to_date).

    Dates are ISO-8601 strings (YYYY-MM-DD).
    """
    label = timeframe.strip().upper()
    if label not in TIMEFRAME_LABELS:
        raise ValueError(f"Invalid timeframe '{timeframe}'")

    end = (now or datetime.now(UTC)).date()
    mapping: dict[str, tuple[str, int]] = {
        "1D": ("5minute", 1),
        "5D": ("15minute", 5),
        "1M": ("day", 30),
        "3M": ("day", 90),
        "6M": ("day", 180),
        "1Y": ("day", 365),
        "3Y": ("week", 365 * 3),
        "5Y": ("week", 365 * 5),
    }
    interval, days = mapping[label]
    start = end - timedelta(days=days)
    return interval, start.isoformat(), end.isoformat()


def yahoo_interval_for(interval: str) -> str:
    """Map API interval to yfinance interval string."""
    return {
        "minute": "1m",
        "5minute": "5m",
        "15minute": "15m",
        "day": "1d",
        "week": "1wk",
        "month": "1mo",
    }.get(interval, "1d")


def filter_candles_by_date(
    candles: list,
    *,
    from_date: str | None,
    to_date: str | None,
    date_attr: str = "date",
) -> list:
    """Filter candle objects by inclusive date range (YYYY-MM-DD prefix match)."""
    if not from_date and not to_date:
        return candles

    filtered = []
    for candle in candles:
        ts = getattr(candle, date_attr, None) or ""
        day = ts[:10]
        if from_date and day < from_date:
            continue
        if to_date and day > to_date:
            continue
        filtered.append(candle)
    return filtered
