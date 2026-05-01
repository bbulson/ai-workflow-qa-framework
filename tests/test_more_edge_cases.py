"""
Extended edge-case and contract tests.

Covers:
- Empty / whitespace-only prompts
- Oversized payloads
- Special characters and emoji (unicode)
- Null / missing prompt field
- Response schema validation
"""
import pytest

from mock_server.chatbot_mock import MAX_PROMPT_LENGTH


# ── Boundary: empty & whitespace ────────────────────────────────────────────

def test_empty_prompt(client):
    """Exact empty string → 400 with an error message."""
    response = client.send_prompt("")
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert isinstance(data["error"], str)
    assert len(data["error"]) > 0
    assert data["error"] == "Prompt is empty"


@pytest.mark.parametrize("blank", [
    " ",          # single space
    "   ",        # multiple spaces
    "\t",         # tab
    "\n",         # newline
    "  \t\n  ",   # mixed whitespace
])
def test_whitespace_only_prompt(client, blank):
    """
    Any prompt that is only whitespace trims to an empty string.
    The mock's `prompt.strip() == ''` guard catches all of these → 400.
    """
    response = client.send_prompt(blank)
    assert response.status_code == 400
    assert response.json()["error"] == "Prompt is empty"


# ── Boundary: length contract ────────────────────────────────────────────────

def test_prompt_at_max_length_is_accepted(client):
    """Exactly MAX_PROMPT_LENGTH characters should be accepted."""
    prompt = "A" * MAX_PROMPT_LENGTH
    response = client.send_prompt(prompt)
    assert response.status_code == 200


def test_prompt_over_max_length_is_rejected(client):
    """MAX_PROMPT_LENGTH + 1 characters should be rejected with 413."""
    prompt = "A" * (MAX_PROMPT_LENGTH + 1)
    response = client.send_prompt(prompt)
    assert response.status_code == 413
    data = response.json()
    assert "error" in data
    assert isinstance(data["error"], str)
    assert len(data["error"]) > 0


# ── Boundary: null / missing field ───────────────────────────────────────────

def test_null_prompt(client):
    """None serialises to JSON null → 400 (prompt is None guard)."""
    response = client.send_prompt(None)
    assert response.status_code == 400
    assert response.json()["error"] == "Prompt is null"


# ── Unicode & special characters ─────────────────────────────────────────────

@pytest.mark.parametrize("prompt", [
    "こんにちは",                          # Japanese
    "café naïve résumé",                  # Latin accents
    "مرحبا",                               # Arabic
    "👋 Hello 🌍",                        # Emoji
    "🔥😂💀",                             # Emoji-only (non-empty, non-blank)
    "SELECT * FROM users; DROP TABLE;",   # SQL injection-like string
    "<script>alert('xss')</script>",      # HTML injection-like string
    "\u200b\u200c\u200d",                  # Zero-width characters (non-blank after strip? no — these are not whitespace)
])
def test_unicode_and_special_characters(client, prompt):
    """
    Contract: any non-empty prompt string (including unicode and symbols)
    is accepted unless it violates explicit validation rules (null/blank/length).
    """
    response = client.send_prompt(prompt)
    assert response.status_code == 200, f"Unexpected status for prompt: {prompt!r}"


def test_special_characters_valid_prompt(client):
    """Emoji mixed with text is a valid non-empty prompt → 200."""
    response = client.send_prompt("🚀 Test with Emojis and Symbols!@#$")
    assert response.status_code == 200


# ── Response schema validation ───────────────────────────────────────────────

def test_response_schema_valid_prompt(client):
    """
    A successful response must contain exactly one key: "response",
    and its value must be a non-empty string.

    Without this test, a response like {"foo": 123} would make
    test_api_available pass while silently breaking callers.
    """
    response = client.send_prompt("Hello")
    assert response.status_code == 200

    data = response.json()
    assert set(data.keys()) == {"response"}, (
        f"Unexpected response shape: {data}"
    )
    assert isinstance(data["response"], str)
    assert len(data["response"]) > 0


def test_response_schema_error_prompt(client):
    """
    Flexible error schema contract:
    a 4xx response must include an "error" key containing a non-empty string.
    Additional keys are allowed.
    """
    response = client.send_prompt("")
    assert response.status_code == 400

    data = response.json()
    assert "error" in data, f"Missing 'error' key in: {data}"
    assert isinstance(data["error"], str)
    assert len(data["error"]) > 0
