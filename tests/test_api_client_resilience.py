"""
AIClient behavior when the transport layer fails or returns non-JSON bodies.

Uses unittest.mock so no real HTTP or requests_mock route is required.
"""
from unittest.mock import MagicMock, patch

import pytest
import requests

from framework.api_client import AIClient


@pytest.fixture
def bare_client():
    return AIClient("https://localhost:5000")


def test_connect_timeout_propagates(bare_client):
    with patch(
        "framework.api_client.requests.post",
        side_effect=requests.exceptions.ConnectTimeout(),
    ):
        with pytest.raises(requests.exceptions.ConnectTimeout):
            bare_client.send_prompt("hello")


def test_connection_error_propagates(bare_client):
    with patch(
        "framework.api_client.requests.post",
        side_effect=requests.exceptions.ConnectionError("refused"),
    ):
        with pytest.raises(requests.exceptions.ConnectionError):
            bare_client.send_prompt("hello")


def test_read_timeout_propagates(bare_client):
    with patch(
        "framework.api_client.requests.post",
        side_effect=requests.exceptions.ReadTimeout(),
    ):
        with pytest.raises(requests.exceptions.ReadTimeout):
            bare_client.send_prompt("hello")


def test_non_json_error_body_still_returns_response(bare_client):
    fake = MagicMock()
    fake.status_code = 502
    fake.text = "<html><body>Bad Gateway</body></html>"
    fake.elapsed.total_seconds.return_value = 0.05
    fake.json.side_effect = ValueError("No JSON")

    with patch("framework.api_client.requests.post", return_value=fake):
        r = bare_client.send_prompt("hello")

    assert r.status_code == 502
    assert "html" in r.text.lower()
