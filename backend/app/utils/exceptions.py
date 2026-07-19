"""Domain-specific exceptions for InvestIQ."""


class InvestIQError(Exception):
    """Base exception for all application errors."""


class ConfigurationError(InvestIQError):
    """Raised when required configuration (e.g. API keys) is missing."""


class TickerNotFoundError(InvestIQError):
    """Raised when a ticker symbol cannot be resolved."""


class ExternalServiceError(InvestIQError):
    """Raised when an upstream API (FMP, Yahoo) fails or returns invalid data."""


class ReportNotFoundError(InvestIQError):
    """Raised when a stored research report cannot be found."""


class KiteAuthError(InvestIQError):
    """Raised when Zerodha OAuth is missing, invalid, or expired."""


class KiteNotEnabledError(InvestIQError):
    """Raised when Kite MCP integration is disabled."""


class KiteBlockedToolError(InvestIQError):
    """Raised when a blocked Kite MCP tool is invoked."""


class KiteServiceError(InvestIQError):
    """Raised when Kite MCP returns an error or is unreachable."""


class NseBseMcpNotEnabledError(InvestIQError):
    """Raised when NSE/BSE MCP integration is disabled."""


class NseBseMcpServiceError(InvestIQError):
    """Raised when NSE/BSE MCP returns an error or is unreachable."""


class TapetideMcpNotEnabledError(InvestIQError):
    """Raised when Tapetide MCP integration is disabled."""


class TapetideMcpServiceError(InvestIQError):
    """Raised when Tapetide MCP returns an error or is unreachable."""


class GoogleDriveNotConnectedError(InvestIQError):
    """Raised when Google Drive MCP integration is disabled or unavailable."""


class GoogleDriveServiceError(InvestIQError):
    """Raised when Google Drive MCP returns an error or is unreachable."""
