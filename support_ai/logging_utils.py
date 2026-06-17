"""Minimal structured logging helpers for Zycus Support AI."""
from __future__ import annotations

import logging
import os


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger configured from LOG_LEVEL env var.

    Usage:
        from support_ai.logging_utils import get_logger
        _log = get_logger(__name__)
    """
    level_name = os.getenv("LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger
