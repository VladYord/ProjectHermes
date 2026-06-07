"""Hermes logging setup."""

from __future__ import annotations

import logging
import sys

from hermes.config import get_config


def setup_logging() -> None:
    """Configure logging from the Hermes config."""
    cfg = get_config().logging

    logging.basicConfig(
        level=cfg.level.upper(),
        format=cfg.format,
        stream=sys.stdout,
    )
    # Quiet noisy third-party loggers
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name, prefixed with 'hermes.'."""
    return logging.getLogger(f"hermes.{name}")
