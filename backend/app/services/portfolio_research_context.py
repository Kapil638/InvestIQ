"""Format Kite portfolio holdings for research crew institutional context."""

from __future__ import annotations

from app.schemas.portfolio import PortfolioHolding
from app.services.advisor_utils import bare_symbol


def format_portfolio_context_for_research(
    holdings: list[PortfolioHolding],
    *,
    research_ticker: str,
) -> str | None:
    """
    Build a compact PORTFOLIO_CONTEXT block for ResearchContext.

    Highlights whether the researched ticker is already owned and overall
    concentration so recommendation agents can adjust allocation language.
    Returns None when there are no usable holdings.
    """
    if not holdings:
        return None

    target = bare_symbol(research_ticker).upper()
    total_value = sum(h.current_value or 0.0 for h in holdings)
    owned = [
        h
        for h in holdings
        if bare_symbol(h.symbol).upper() == target
    ]

    lines = [
        "User Zerodha portfolio (read-only Kite holdings).",
        f"Holdings count: {len(holdings)}",
    ]
    if total_value > 0:
        lines.append(f"Total portfolio value (approx): {total_value:,.0f}")

    if owned:
        for h in owned:
            weight = None
            if total_value > 0 and h.current_value is not None:
                weight = (h.current_value / total_value) * 100
            bits = [
                f"ALREADY OWNED: {h.symbol}",
                f"qty={h.quantity}" if h.quantity is not None else None,
                f"avg={h.average_price}" if h.average_price is not None else None,
                f"ltp={h.last_price}" if h.last_price is not None else None,
                f"pnl%={h.pnl_percent:.1f}" if h.pnl_percent is not None else None,
                f"weight={weight:.1f}%" if weight is not None else None,
            ]
            lines.append(" | ".join(b for b in bits if b))
        lines.append(
            "Recommendation must acknowledge existing exposure and whether to "
            "add, hold, trim, or exit — not treat the name as a fresh entry only."
        )
    else:
        lines.append(f"NOT CURRENTLY HELD: {target}")
        lines.append(
            "Allocation suggestion should assume a new position sized against "
            "existing portfolio concentration."
        )

    # Top positions for diversification context (exclude tiny noise)
    ranked = sorted(
        holdings,
        key=lambda h: h.current_value or 0.0,
        reverse=True,
    )[:8]
    lines.append("Top holdings by value:")
    for h in ranked:
        weight = (
            ((h.current_value / total_value) * 100)
            if total_value > 0 and h.current_value is not None
            else None
        )
        name = h.company_name or h.symbol
        weight_bit = f", {weight:.1f}%" if weight is not None else ""
        pnl_bit = f", pnl {h.pnl_percent:.1f}%" if h.pnl_percent is not None else ""
        lines.append(f"- {h.symbol} ({name}){weight_bit}{pnl_bit}")

    sector_weights: dict[str, float] = {}
    if total_value > 0:
        for h in holdings:
            if not h.sector or h.current_value is None:
                continue
            sector_weights[h.sector] = sector_weights.get(h.sector, 0.0) + h.current_value
        if sector_weights:
            lines.append("Sector exposure (approx):")
            for sector, value in sorted(sector_weights.items(), key=lambda x: -x[1])[:6]:
                lines.append(f"- {sector}: {(value / total_value) * 100:.1f}%")

    return "\n".join(lines)
