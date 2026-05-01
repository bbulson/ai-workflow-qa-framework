"""
Contract tests through AIClient + requests_mock (mirrors Flask rules in conftest).
"""
import pytest

from mock_server.chatbot_mock import MAX_PROMPT_LENGTH


def test_missing_prompt_key_via_mock(client):
    for payload in ({}, {"other": 1}):
        r = client.send_chat_payload(payload)
        assert r.status_code == 400
        assert r.json()["error"] == "Prompt is null"


@pytest.mark.parametrize(
    "bad_prompt",
    [123, True, False, [], {}, ["a"]],
)
def test_non_string_prompt_via_mock(client, bad_prompt):
    r = client.send_chat_payload({"prompt": bad_prompt})
    assert r.status_code == 400
    assert r.json()["error"] == "Prompt must be a string"


def test_malformed_json_raw_via_mock(client):
    r = client.send_chat_raw("{not json")
    assert r.status_code == 400
    assert r.json()["error"] == "Prompt is null"


def test_multibyte_length_boundary_via_mock(client):
    token = "😀"
    ok = token * MAX_PROMPT_LENGTH
    r = client.send_chat_payload({"prompt": ok})
    assert r.status_code == 200

    r = client.send_chat_payload({"prompt": token * (MAX_PROMPT_LENGTH + 1)})
    assert r.status_code == 413
    assert "error" in r.json()
