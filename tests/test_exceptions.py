"""Tests for the custom exception hierarchy."""
from support_ai.exceptions import (
    ConfigurationError,
    DataSourceError,
    KBRetrievalError,
    TriageError,
    ZycusBaseError,
)


def test_all_exceptions_derive_from_base():
    for exc_class in (ConfigurationError, DataSourceError, TriageError, KBRetrievalError):
        assert issubclass(exc_class, ZycusBaseError)


def test_base_error_is_exception():
    assert issubclass(ZycusBaseError, Exception)


def test_configuration_error_raises_and_catches():
    try:
        raise ConfigurationError("LLM_PROVIDER is invalid")
    except ZycusBaseError as exc:
        assert "LLM_PROVIDER" in str(exc)


def test_data_source_error_message():
    exc = DataSourceError("Cannot read data/accounts.json")
    assert "accounts.json" in str(exc)
