import os
import json
import sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL")

# Lazy import — only needed when DATABASE_URL is set
if DATABASE_URL:
    import psycopg2
    import psycopg2.extras


def _is_pg(conn) -> bool:
    """Return True if conn is a psycopg2 connection."""
    if DATABASE_URL:
        return isinstance(conn, psycopg2.extensions.connection)
    return False


def _placeholder(conn) -> str:
    """Return the correct parameter placeholder for the connection type."""
    return "%s" if _is_pg(conn) else "?"


def init_db(db_path="data/qa_results.db"):
    """
    Open and initialise the database.

    - When DATABASE_URL is set (Docker / CI): connects to PostgreSQL.
      Uses SERIAL primary keys and TIMESTAMPTZ; supports true parallel writers.
    - Otherwise: falls back to SQLite with WAL mode for local development.
    """
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        cur = conn.cursor()
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
        cur.close()
        return conn

    # ── SQLite fallback (local dev / unit tests) ──────────────────
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id   INTEGER,
            user_id    INTEGER,
            amount     REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS test_results (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            test_name        TEXT,
            status           TEXT,
            latency_ms       REAL,
            request_payload  TEXT,
            response_payload TEXT,
            response_code    INTEGER,
            environment      TEXT,
            timestamp        DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def log_test_result(conn=None, test_name=None, status=None, latency_ms=None,
                    request_payload=None, response_payload=None,
                    response_code=None, environment=None):

    should_close = False

    if conn is None:
        conn = init_db("data/qa_results.db")
        should_close = True

    ph = _placeholder(conn)
    sql = f"""
        INSERT INTO test_results (
            test_name, status, latency_ms,
            request_payload, response_payload,
            response_code, environment
        ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
    """
    params = (
        test_name,
        status,
        latency_ms,
        json.dumps(request_payload),
        json.dumps(response_payload),
        response_code,
        environment,
    )

    if _is_pg(conn):
        cur = conn.cursor()
        cur.execute(sql, params)
        cur.close()
    else:
        conn.execute(sql, params)

    conn.commit()

    if should_close:
        conn.close()
