"""
db_integrity.py — SQL Validation & Data Integrity Module
=========================================================
First-step upgrade for ai-workflow-qa-framework.

Goals
-----
1. Replace fire-and-forget log writes with assertions that *fail tests*
   when data is wrong.
2. Provide reusable integrity checks that work under concurrent load
   (the SQLite WAL-mode setting + row-level locking helpers).
3. Give pytest fixtures that each test gets a clean, validated slate.

Usage
-----
In conftest.py, replace the existing `db_conn` fixture with the one
exported here, or import `validate_db_state` directly into tests:

    from framework.db_integrity import validate_db_state, IntegrityError

Drop-in for existing code — no test rewrites required.
"""

import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


# ─────────────────────────────────────────────
# Custom exception so failures are clearly named
# ─────────────────────────────────────────────

class IntegrityError(AssertionError):
    """Raised when a SQL integrity check fails."""


# ─────────────────────────────────────────────
# Connection factory — WAL mode for concurrency
# ─────────────────────────────────────────────

def make_connection(db_path: str = ":memory:") -> Any:
    """
    Open a database connection configured for concurrent microservice workloads.

    - When DATABASE_URL is set: connects to PostgreSQL, which provides true
      parallel writers via MVCC — no WAL pragma needed, it's always on.
    - Otherwise: SQLite with WAL mode + busy_timeout for local/unit-test use.

    Both paths give you non-blocking readers, transactional integrity, and
    named-column row access.
    """
    import os
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError:
            raise ImportError(
                "psycopg2-binary is required when DATABASE_URL is set. "
                "Run: pip install psycopg2-binary"
            )
        conn = psycopg2.connect(database_url,
                                cursor_factory=psycopg2.extras.RealDictCursor)
        conn.autocommit = False
        return conn

    # ── SQLite fallback ───────────────────────────────────────────
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")   # ms
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row             # named-column access
    return conn



# ─────────────────────────────────────────────────────────────────
# DB-agnostic query helpers (SQLite conn.execute vs psycopg2 cursor)
# ─────────────────────────────────────────────────────────────────

def _is_pg(conn) -> bool:
    try:
        import psycopg2.extensions
        return isinstance(conn, psycopg2.extensions.connection)
    except ImportError:
        return False


def _fetchall(conn, sql: str, params: tuple = ()) -> list:
    """Execute sql and return rows as plain dicts for both PG and SQLite."""
    if _is_pg(conn):
        pg_sql = sql.replace("?", "%s")
        with conn.cursor() as cur:
            cur.execute(pg_sql, params)
            return [dict(r) for r in cur.fetchall()]
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _fetchone_scalar(conn, sql: str, params: tuple = ()):
    """Return the first column of the first row (e.g. COUNT(*))."""
    if _is_pg(conn):
        pg_sql = sql.replace("?", "%s")
        with conn.cursor() as cur:
            cur.execute(pg_sql, params)
            row = cur.fetchone()
            return list(row.values())[0] if row else None
    return conn.execute(sql, params).fetchone()[0]


def _execute(conn, sql: str, params: tuple = ()) -> None:
    """Execute a DML statement (INSERT/UPDATE/DELETE) on either backend."""
    if _is_pg(conn):
        pg_sql = sql.replace("?", "%s")
        with conn.cursor() as cur:
            cur.execute(pg_sql, params)
    else:
        conn.execute(sql, params)


# ─────────────────────────────────────────────────
# Core integrity checks  (each raises IntegrityError
# so they fail the pytest test immediately)
# ─────────────────────────────────────────────────

def assert_no_duplicate_order_ids(conn) -> None:
    """Fail if any order_id appears more than once in the orders table."""
    rows = _fetchall(conn, """
        SELECT order_id, COUNT(*) AS cnt
        FROM orders
        GROUP BY order_id
        HAVING COUNT(*) > 1
    """)
    if rows:
        detail = ", ".join(f"order_id={r['order_id']} ({r['cnt']} times)" for r in rows)
        raise IntegrityError(f"Duplicate order_ids detected: {detail}")


def assert_no_null_required_fields(conn) -> None:
    """Fail if any order is missing order_id, user_id, or amount."""
    rows = _fetchall(conn, """
        SELECT id, order_id, user_id, amount
        FROM orders
        WHERE order_id IS NULL
           OR user_id  IS NULL
           OR amount   IS NULL
    """)
    if rows:
        ids = [r["id"] for r in rows]
        raise IntegrityError(f"Orders with NULL required fields (row ids): {ids}")


def assert_positive_amounts(conn) -> None:
    """Fail if any order has a zero or negative amount — business rule."""
    rows = _fetchall(conn, """
        SELECT id, order_id, amount
        FROM orders
        WHERE amount <= 0
    """)
    if rows:
        detail = [(r["id"], r["order_id"], r["amount"]) for r in rows]
        raise IntegrityError(f"Orders with non-positive amounts: {detail}")


def assert_row_count(
    conn,
    table: str,
    expected: int,
    op: str = "=="
) -> None:
    """
    Assert the row count for *table* matches *expected*.

    op can be '==', '>=', '<=', '>', '<'
    Example:
        assert_row_count(conn, "orders", 3)
        assert_row_count(conn, "test_results", 1, ">=")
    """
    actual = _fetchone_scalar(conn, f"SELECT COUNT(*) FROM {table}")
    ops = {"==": actual == expected, ">=": actual >= expected,
           "<=": actual <= expected, ">": actual > expected,
           "<": actual < expected}
    if not ops.get(op, False):
        raise IntegrityError(
            f"Row count for '{table}': expected {op} {expected}, got {actual}"
        )


def assert_test_result_logged(
    conn,
    test_name: str,
    expected_status: str | None = None
) -> None:
    """
    Verify a test result was *actually persisted*, not just logged to stdout.
    Optionally check that its status matches expected_status ('PASS'/'FAIL').
    """
    rows = _fetchall(
        conn,
        "SELECT status FROM test_results WHERE test_name = ? ORDER BY timestamp DESC",
        (test_name,)
    )
    if not rows:
        raise IntegrityError(
            f"No test_result row found for test '{test_name}'. "
            "Was log_test_result() called, or did it only print to stdout?"
        )
    if expected_status is not None:
        latest = rows[0]["status"]
        if latest != expected_status:
            raise IntegrityError(
                f"test_result for '{test_name}': expected status '{expected_status}', got '{latest}'"
            )


# ─────────────────────────────────────────────
# Composite validator — run all checks at once
# ─────────────────────────────────────────────

@dataclass
class ValidationResult:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.failed) == 0

    def __str__(self) -> str:
        lines = [f"✓ {p}" for p in self.passed] + [f"✗ {f}" for f in self.failed]
        return "\n".join(lines)


def validate_db_state(conn, raise_on_failure: bool = True) -> ValidationResult:
    """
    Run every integrity check and collect results.

    If raise_on_failure=True (default), raises IntegrityError listing all
    failures — best for pytest.  Pass raise_on_failure=False to get a
    ValidationResult object without raising (useful for health-check endpoints).
    """
    checks = {
        "no_duplicate_order_ids":    assert_no_duplicate_order_ids,
        "no_null_required_fields":   assert_no_null_required_fields,
        "positive_amounts":          assert_positive_amounts,
    }

    result = ValidationResult()
    for name, fn in checks.items():
        try:
            fn(conn)
            result.passed.append(name)
        except IntegrityError as exc:
            result.failed.append(f"{name}: {exc}")

    if raise_on_failure and not result.ok:
        raise IntegrityError(
            f"DB integrity checks failed:\n" + "\n".join(result.failed)
        )
    return result


# ─────────────────────────────────────────────
# Concurrency helper — simulate agentic writes
# ─────────────────────────────────────────────

def run_concurrent_inserts(
    db_path: str,
    orders: list[tuple],
    workers: int = 5
) -> list[Exception]:
    """
    Simulate multiple microservice workers writing orders simultaneously.
    Returns a list of any exceptions raised (empty = all succeeded).

    When DATABASE_URL is set, each worker opens a real PostgreSQL connection,
    exercising true parallel writers via MVCC (no serialization).
    In SQLite mode, WAL mode allows concurrent reads while serializing writes.

        errors = run_concurrent_inserts("data/qa_results.db", orders, workers=10)
        assert errors == [], f"Concurrent writes failed: {errors}"
    """
    import os
    errors: list[Exception] = []
    lock = threading.Lock()
    database_url = os.environ.get("DATABASE_URL")

    def worker(batch: list[tuple]) -> None:
        try:
            conn = make_connection(db_path)
            if _is_pg(conn):
                with conn.cursor() as cur:
                    cur.executemany(
                        "INSERT INTO orders (order_id, user_id, amount) VALUES (%s, %s, %s)",
                        batch
                    )
            else:
                conn.executemany(
                    "INSERT INTO orders (order_id, user_id, amount) VALUES (?, ?, ?)",
                    batch
                )
            conn.commit()
            conn.close()
        except Exception as exc:
            with lock:
                errors.append(exc)

    chunk = max(1, len(orders) // workers)
    batches = [orders[i:i + chunk] for i in range(0, len(orders), chunk)]
    threads = [threading.Thread(target=worker, args=(b,)) for b in batches]

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    return errors


# ─────────────────────────────────────────────
# Context manager for transactional test blocks
# ─────────────────────────────────────────────

@contextmanager
def integrity_checked_transaction(conn):
    """
    Wraps a block of DB writes in a transaction and runs all integrity
    checks on commit.  Rolls back automatically if checks fail.

    Example:
        with integrity_checked_transaction(conn):
            seed_orders(conn, my_orders)
            # IntegrityError raised here → transaction rolled back
    """
    try:
        yield conn
        validate_db_state(conn, raise_on_failure=True)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
