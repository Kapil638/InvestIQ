"""Public market ticker for the pre-login page."""

from pydantic import BaseModel


class TickerItem(BaseModel):
    symbol: str
    name: str
    price: float | None = None
    change_percent: float | None = None


class TickerResponse(BaseModel):
    market_open: bool
    as_of: str
    items: list[TickerItem]
