from __future__ import annotations

from support_ai.redaction import redact_pii, redact_record


# 1 — email redaction
def test_email_redacted():
    result = redact_pii("Contact support@example.com for help.")
    assert "[EMAIL]" in result
    assert "support@example.com" not in result


# 2 — phone redaction
def test_phone_redacted():
    assert "[PHONE]" in redact_pii("Call 555-867-5309 now.")
    assert "[PHONE]" in redact_pii("Reach us at +1 (800) 123-4567.")


# 3 — IPv4 redaction
def test_ip_redacted():
    result = redact_pii("Server at 192.168.1.100 is down.")
    assert "[IP]" in result
    assert "192.168.1.100" not in result


# 4 — 24+ char alphanumeric token redaction
def test_long_token_redacted():
    token = "aB3dEf7hIjKlMnOpQrStUvWx"  # 24 chars
    result = redact_pii(f"API key: {token}")
    assert "[TOKEN]" in result
    assert token not in result


# 5 — recursive redaction on dicts and lists
def test_recursive_redact_record():
    data = {
        "email": "admin@corp.io",
        "notes": ["call 555-123-4567", "ip 10.0.0.1"],
        "nested": {"token": "AAABBBCCCDDDEEEFFFGGGHHH"},
    }
    result = redact_record(data)
    assert "[EMAIL]" in result["email"]
    assert "[PHONE]" in result["notes"][0]
    assert "[IP]" in result["notes"][1]
    assert "[TOKEN]" in result["nested"]["token"]


# 6 — normal words are preserved
def test_normal_words_preserved():
    text = "The SSO login failed for the user."
    assert redact_pii(text) == text
