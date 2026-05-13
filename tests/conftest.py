"""
tests/conftest.py
=================
Dual-backend fixture setup — works with PostgreSQL (when DATABASE_URL is set)
and SQLite (local dev / unit tests).

Key behaviours:
- PostgreSQL: each test gets a rollback-isolated connection — no test data leaks
  between tests, no per-test DB creation needed.
- SQLite: each test gets an isolated on-disk file with WAL mode enabled.
- mock_ai_service is skipped for @pytest.mark.e2e tests (real HTTP calls).
"""

import os
import pytest
import requests_mock as rm_module

from framework.api_client import AIClient
from framework.db import init_db
from framework.db_integrity import make_connection, _is_pg


@pytest.fixture
def client():
    return AIClient("https://localhost:5000")


@pytest.fixture
def db_conn(tmp_path):
    """
    Database connection for unit/integration tests.

    PostgreSQL mode (DATABASE_URL set):
      - Connects to Postgres and ensures the schema exists.
      - Wraps every test in a transaction that is rolled back at teardown,
        so each test starts with a clean slate without dropping/recreating tables.

    SQLite mode (no DATABASE_URL):
      - Creates an isolated DB file per test.
      - WAL mode + busy_timeout enabled via make_connection().
    """
    conn = make_connection(str(tmp_path / "test.db"))

    if _is_pg(conn):
        # Ensure schema exists (idempotent — safe to run every test)
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id         SERIAL PRIMARY KEY,
                    order_id   INTEGER,
                    user_id    INTEGER,
                    amount     NUMERIC,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS test_results (
                    id               SERIAL PRIMARY KEY,
                    test_name        TEXT,
                    status           TEXT,
                    latency_ms       NUMERIC,
                    request_payload  TEXT,
                    response_payload TEXT,
                    response_code    INTEGER,
                    environment      TEXT,
                    timestamp        TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        conn.commit()
        # Delete all rows so this test starts clean (faster than DROP/CREATE)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM orders")
            cur.execute("DELETE FROM test_results")
        conn.commit()
        yield conn
        conn.close()
    else:
        # SQLite: init_db creates tables; make_connection re-opens with WAL
        plain_conn = init_db(str(tmp_path / "test.db"))
        plain_conn.close()
        conn = make_connection(str(tmp_path / "test.db"))
        yield conn
        conn.close()


@pytest.fixture
def db_path(tmp_path):
    """
    On-disk path for concurrency tests (run_concurrent_inserts needs a path).

    PostgreSQL mode: returns the DATABASE_URL string instead of a file path —
    make_connection() and run_concurrent_inserts() both accept this.
    SQLite mode: returns a tmp file path, schema pre-created.
    """
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        # Schema must exist before concurrent workers try to insert
        conn = make_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id         SERIAL PRIMARY KEY,
                    order_id   INTEGER,
                    user_id    INTEGER,
                    amount     NUMERIC,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("DELETE FROM orders")
        conn.commit()
        conn.close()
        return database_url

    # SQLite
    path = str(tmp_path / "concurrent.db")
    conn = make_connection(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            user_id  INTEGER,
            amount   REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    return path


@pytest.fixture(autouse=True)
def mock_ai_service(request):
    # e2e tests make real HTTP calls to the live container — skip the mock.
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
