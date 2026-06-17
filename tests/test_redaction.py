"""Tests for PII redaction helpers."""
from support_ai.redaction import redact_credit_card


def test_redact_plain_16_digit_card():
    result = redact_credit_card("Card: 4111111111111111 expired")
    assert "4111111111111111" not in result
    assert "[REDACTED-CC]" in result


def test_redact_dashed_card():
    result = redact_credit_card("CC: 4111-1111-1111-1111")
    assert "[REDACTED-CC]" in result


def test_redact_spaced_card():
    result = redact_credit_card("Number: 4111 1111 1111 1111 on file")
    assert "[REDACTED-CC]" in result


def test_no_false_positive_order_number():
    result = redact_credit_card("Order #12345 received")
    assert "[REDACTED-CC]" not in result


def test_no_false_positive_short_number():
    result = redact_credit_card("Ticket ID: 123456789")
    assert "[REDACTED-CC]" not in result
