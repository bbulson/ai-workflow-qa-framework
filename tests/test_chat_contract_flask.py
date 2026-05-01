"""
HTTP contract tests against the Flask mock app (same code path as Docker image).

Uses Flask's test client so JSON parsing, methods, and Content-Type behave like production.
"""
import json
import unicodedata

import pytest

from mock_server.chatbot_mock import MAX_PROMPT_LENGTH, app


@pytest.fixture
def flask_client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def _assert_flexible_error(data):
    assert "error" in data
    assert isinstance(data["error"], str)
    assert len(data["error"]) > 0


def test_missing_prompt_key_returns_null_error(flask_client):
    for payload in ({}, {"other": "x"}):
        resp = flask_client.post("/chat", json=payload)
        assert resp.status_code == 400
        data = resp.get_json()
        _assert_flexible_error(data)
        assert data["error"] == "Prompt is null"


def test_explicit_null_prompt(flask_client):
    resp = flask_client.post("/chat", json={"prompt": None})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Prompt is null"


@pytest.mark.parametrize(
    "bad_prompt",
    [123, True, False, [], {}, ["x"], {"a": 1}],
)
def test_non_string_prompt_must_be_string(flask_client, bad_prompt):
    resp = flask_client.post("/chat", json={"prompt": bad_prompt})
    assert resp.status_code == 400
    data = resp.get_json()
    _assert_flexible_error(data)
    assert data["error"] == "Prompt must be a string"


def test_extra_json_keys_still_success(flask_client):
    resp = flask_client.post(
        "/chat",
        json={"prompt": "hi", "meta": {"trace": "abc"}},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data.keys()) == {"response"}
    assert "hi" in data["response"]


def test_malformed_json_body_treated_as_missing_prompt(flask_client):
    resp = flask_client.post(
        "/chat",
        data="{not valid json",
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Prompt is null"


def test_wrong_content_type_plain_text(flask_client):
    resp = flask_client.post(
        "/chat",
        data="just text",
        content_type="text/plain",
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Prompt is null"


def test_prompt_length_boundary_multibyte(flask_client):
    token = "😀"
    ok = token * MAX_PROMPT_LENGTH
    assert len(ok) == MAX_PROMPT_LENGTH
    resp = flask_client.post("/chat", json={"prompt": ok})
    assert resp.status_code == 200

    too_long = token * (MAX_PROMPT_LENGTH + 1)
    resp = flask_client.post("/chat", json={"prompt": too_long})
    assert resp.status_code == 413
    _assert_flexible_error(resp.get_json())


def test_unicode_normalization_nfd_still_accepted(flask_client):
    nfd = unicodedata.normalize("NFD", "café")
    resp = flask_client.post("/chat", json={"prompt": nfd})
    assert resp.status_code == 200


@pytest.mark.parametrize("ws", ["\r", "\f", "\v", "\r\n\v\f"])
def test_ascii_control_whitespace_only_rejected(flask_client, ws):
    resp = flask_client.post("/chat", json={"prompt": ws})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Prompt is empty"


def test_nbsp_only_stripped_as_whitespace(flask_client):
    """NBSP (U+00A0) is stripped by str.strip() in CPython; all-NBSP is empty."""
    prompt = "\u00a0" * 5
    assert len(prompt.strip()) == 0
    resp = flask_client.post("/chat", json={"prompt": prompt})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Prompt is empty"


def test_post_chat_json_content_type(flask_client):
    resp = flask_client.post("/chat", json={"prompt": "ok"})
    assert resp.status_code == 200
    assert "application/json" in (resp.headers.get("Content-Type") or "").lower()


def test_get_chat_not_allowed(flask_client):
    resp = flask_client.get("/chat")
    assert resp.status_code == 405


def test_put_chat_not_allowed(flask_client):
    resp = flask_client.put("/chat", json={"prompt": "x"})
    assert resp.status_code == 405


def test_post_health_not_allowed(flask_client):
    resp = flask_client.post("/health", json={})
    assert resp.status_code == 405
