"""Tests for the centralised logger factory."""
import logging
import os
from unittest.mock import patch

from support_ai.logging_utils import get_logger


def test_get_logger_returns_logger_instance():
    logger = get_logger("test.module")
    assert isinstance(logger, logging.Logger)


def test_get_logger_name_matches():
    logger = get_logger("support_ai.triage")
    assert logger.name == "support_ai.triage"


def test_get_logger_respects_log_level_env():
    with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
        logger = get_logger("test.debug_level")
    assert logger.level == logging.DEBUG


def test_get_logger_default_level_is_warning():
    with patch.dict(os.environ, {}, clear=True):
        # Remove LOG_LEVEL if set
        os.environ.pop("LOG_LEVEL", None)
        logger = get_logger("test.default_level_check")
    assert logger.level in (logging.WARNING, 0)  # 0 = NOTSET inherits parent
