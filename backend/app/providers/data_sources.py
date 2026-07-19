"""Canonical data-source slugs returned by InvestIQ APIs."""

TAPETIDE_MCP_SOURCE = "tapetide_mcp"
LOCAL_MASTER_SOURCE = "local_master"
NSE_SOURCE = "nse"
KITE_SOURCE = "kite"
YAHOO_SOURCE = "yahoo"

# Deprecated – kept for legacy response normalization only.
NSE_BSE_MCP_SOURCE = "nse_bse_mcp"

SOURCE_LABELS: dict[str, str] = {
    TAPETIDE_MCP_SOURCE: "Tapetide NSE/BSE MCP",
    LOCAL_MASTER_SOURCE: "Local Master",
    NSE_SOURCE: "NSE",
    KITE_SOURCE: "Kite",
    YAHOO_SOURCE: "Yahoo",
    NSE_BSE_MCP_SOURCE: "Tapetide NSE/BSE MCP",
}


def source_label(slug: str) -> str:
    return SOURCE_LABELS.get(slug, slug)


def normalize_source_slug(value: str) -> str:
    """Map legacy human-readable labels to slug form."""
    legacy = {
        "Kite Connect": KITE_SOURCE,
        "Yahoo Finance": YAHOO_SOURCE,
        "NSE/BSE MCP": TAPETIDE_MCP_SOURCE,
        "Tapetide NSE/BSE MCP": TAPETIDE_MCP_SOURCE,
        NSE_BSE_MCP_SOURCE: TAPETIDE_MCP_SOURCE,
    }
    return legacy.get(value, value)
