"""
tests/conftest.py  (updated)
=============================
Drop-in replacement for the existing conftest.  The only changes:

1. `db_conn` now uses `make_connection()` from db_integrity, which enables
   WAL journal mode, busy_timeout, and foreign key enforcement — the
   minimum needed for concurrency-safe tests.

2. Everything else (client fixture, mock_ai_service) is unchanged.
"""

import pytest
import requests_mock as rm_module
from framework.api_client import AIClient
from framework.db import init_db
from framework.db_integrity import make_connection


@pytest.fixture
def client():
    return AIClient("https://localhost:5000")


@pytest.fixture
def db_conn(tmp_path):
    """
    Provides a WAL-mode SQLite connection with the full schema initialised.
    Each test gets a clean, isolated database file.
    """
    db_file = str(tmp_path / "test.db")

    # init_db creates the schema and returns a plain sqlite3 connection.
    # Close it and re-open via make_connection to get WAL + busy_timeout.
    plain_conn = init_db(db_file)
    plain_conn.close()

    conn = make_connection(db_file)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def mock_ai_service(request):
    # e2e tests make real HTTP calls to the live container — requests_mock
    # must not intercept them. Skip the mock entirely for any test marked e2e.
    if request.node.get_closest_marker("e2e"):
        yield None
        return

    with rm_module.Mocker() as m:

        def dynamic_response(request, context):
            data = request.json()
            prompt = data.get("prompt")

            if prompt is None:
                context.status_code = 400
                return {"error": "Prompt is null"}

            if isinstance(prompt, str) and prompt.strip() == "":
                context.status_code = 400
                return {"error": "Prompt is empty"}

            if isinstance(prompt, str) and len(prompt) > 5000:
                context.status_code = 413
                return {"error": "Payload too large"}

            context.status_code = 200
            return {"response": f"Mocked response: {prompt}"}

        m.post("https://localhost:5000/chat", json=dynamic_response)
        m.get("https://localhost:5000/health", status_code=200)

        yield m
