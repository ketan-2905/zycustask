"""Custom exception hierarchy for Zycus Support AI.

All application-level exceptions derive from ZycusBaseError so callers
can catch at the appropriate granularity without importing every leaf class.
"""
from __future__ import annotations


class ZycusBaseError(Exception):
    """Root exception for all application-level errors."""


class ConfigurationError(ZycusBaseError):
    """Raised when required configuration is missing or invalid."""


class DataSourceError(ZycusBaseError):
    """Raised when a data source (file, API) cannot be read."""


class TriageError(ZycusBaseError):
    """Raised when ticket triage fails in an unexpected way."""


class KBRetrievalError(ZycusBaseError):
    """Raised when knowledge-base loading or retrieval fails."""
