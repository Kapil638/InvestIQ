"""Central logging configuration."""

import logging
import sys


def setup_logging(level: str | int = logging.INFO) -> None:
    """Configure application-wide logging once at startup."""
    if isinstance(level, str):
        resolved = getattr(logging, level.upper(), logging.INFO)
    else:
        resolved = level

    logging.basicConfig(
        level=resolved,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
