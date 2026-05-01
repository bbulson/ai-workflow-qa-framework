"""
Edge-case tests — all use the `client` fixture from conftest.py so every
request is intercepted by the `mock_ai_service` fixture.

Previously this file instantiated AIClient() at module level, which bypassed
the requests_mock entirely and sent real HTTP calls to a server that isn't
running in CI. That caused the empty-prompt test to receive a 200 instead of
the expected 400.
"""
import pytest


def test_empty_prompt(client):
    """Empty string → mock returns 400 (prompt.strip() == '')."""
    response = client.send_prompt("")
    assert response.status_code == 400
    assert response.json()["error"] == "Prompt is empty"


def test_gibberish_prompt(client):
    """Non-empty strings are valid inputs → 200."""
    response = client.send_prompt("asdkfjasldkfj")
    assert response.status_code == 200
