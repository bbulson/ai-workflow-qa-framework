"""
tests/test_db_integrity.py
==========================
Validates data persistence and integrity for the AI workflow QA framework.
Covers: persistence verification, business rule enforcement, concurrency
safety, and the integration between log_test_result() and actual DB writes.

Run:
    pytest tests/test_db_integrity.py -v
"""

import os
import threading
import pytest

from framework.db import init_db, log_test_result
from framework.db_utils import seed_orders, clear_orders, find_duplicate_order_ids
from framework.db_integrity import (
    IntegrityError,
    assert_no_duplicate_order_ids,
    assert_no_null_required_fields,
    assert_positive_amounts,
    assert_row_count,
    assert_test_result_logged,
    validate_db_state,
    run_concurrent_inserts,
    integrity_checked_transaction,
    make_connection,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def db_conn(tmp_path):
    """Fresh in-process DB for every test — WAL mode enabled."""
    db_file = str(tmp_path / "test.db")
    conn = make_connection(db_file)           # WAL + busy_timeout + FK
    init_db.__wrapped__(conn) if hasattr(init_db, "__wrapped__") else None

    # Ensure tables exist (init_db accepts a path, so open a second conn
    # to create schema, then hand back our WAL conn)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            user_id  INTEGER,
            amount   REAL,
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
    yield conn
    conn.close()


@pytest.fixture
def db_path(tmp_path):
    """Path to an on-disk DB for concurrency tests."""
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


# ══════════════════════════════════════════════
# 1. PERSISTENCE — data written must be readable
# ══════════════════════════════════════════════

class TestPersistence:

    def test_seeded_orders_are_persisted(self, db_conn):
        """seed_orders() must actually write rows — not just print them."""
        seed_orders(db_conn, [(1, 10, 100.0), (2, 11, 200.0)])
        assert_row_count(db_conn, "orders", 2)

    def test_log_test_result_persists_to_db(self, db_conn):
        """
        Key regression: log_test_result used to only write to stdout.
        Confirm it inserts a row into test_results.
        """
        log_test_result(
            conn=db_conn,
            test_name="test_sample_api_call",
            status="PASS",
            latency_ms=42.0,
            request_payload={"prompt": "hello"},
            response_payload={"response": "hi"},
            response_code=200,
            environment="test",
        )
        assert_test_result_logged(db_conn, "test_sample_api_call", expected_status="PASS")

    def test_clear_orders_removes_all_rows(self, db_conn):
        seed_orders(db_conn, [(1, 10, 50.0)])
        clear_orders(db_conn)
        assert_row_count(db_conn, "orders", 0)

    def test_data_survives_reconnect(self, tmp_path):
        """Simulate a service restart — data must survive across connections."""
        db_file = str(tmp_path / "persist.db")

        conn1 = make_connection(db_file)
        conn1.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER, user_id INTEGER, amount REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        seed_orders(conn1, [(99, 1, 999.0)])
        conn1.close()

        conn2 = make_connection(db_file)
        count = conn2.execute("SELECT COUNT(*) FROM orders WHERE order_id=99").fetchone()[0]
        conn2.close()
        assert count == 1, "Row was lost after reconnect — persistence failure"


# ══════════════════════════════════════════════
# 2. INTEGRITY — business rule enforcement
# ══════════════════════════════════════════════

class TestIntegrityRules:

    def test_duplicate_order_ids_detected(self, db_conn):
        seed_orders(db_conn, [(1001, 1, 50.0), (1001, 2, 75.0)])
        with pytest.raises(IntegrityError, match="Duplicate order_ids"):
            assert_no_duplicate_order_ids(db_conn)

    def test_clean_orders_pass_duplicate_check(self, db_conn):
        seed_orders(db_conn, [(1001, 1, 50.0), (1002, 2, 75.0)])
        assert_no_duplicate_order_ids(db_conn)   # must not raise

    def test_null_order_id_detected(self, db_conn):
        db_conn.execute("INSERT INTO orders (order_id, user_id, amount) VALUES (NULL, 1, 10.0)")
        db_conn.commit()
        with pytest.raises(IntegrityError, match="NULL required fields"):
            assert_no_null_required_fields(db_conn)

    def test_zero_amount_detected(self, db_conn):
        seed_orders(db_conn, [(5001, 1, 0.0)])
        with pytest.raises(IntegrityError, match="non-positive amounts"):
            assert_positive_amounts(db_conn)

    def test_negative_amount_detected(self, db_conn):
        seed_orders(db_conn, [(5002, 1, -99.99)])
        with pytest.raises(IntegrityError, match="non-positive amounts"):
            assert_positive_amounts(db_conn)

    def test_composite_validator_catches_multiple_failures(self, db_conn):
        """validate_db_state should surface ALL failures in one shot."""
        seed_orders(db_conn, [(1001, 1, 50.0), (1001, 2, -10.0)])
        result = validate_db_state(db_conn, raise_on_failure=False)
        assert not result.ok
        assert len(result.failed) >= 2   # duplicates + negative amount


# ══════════════════════════════════════════════
# 3. CONCURRENCY — consistency under parallel writes
# ══════════════════════════════════════════════

class TestConcurrency:

    def test_concurrent_writes_no_data_loss(self, db_path):
        """
        10 workers each insert 10 orders simultaneously.
        All 100 rows must land — no silent drops due to lock contention.
        """
        orders = [(i, i % 5, float(i * 10)) for i in range(1, 101)]
        errors = run_concurrent_inserts(db_path, orders, workers=10)
        assert errors == [], f"Concurrent insert errors: {errors}"

        conn = make_connection(db_path)
        assert_row_count(conn, "orders", 100)
        conn.close()

    def test_concurrent_writes_no_corruption(self, db_path):
        """
        After parallel inserts, every expected order_id must be present
        (no partial writes, no phantom rows).
        """
        orders = [(i, 1, 1.0) for i in range(200, 250)]
        run_concurrent_inserts(db_path, orders, workers=5)

        conn = make_connection(db_path)
        saved_ids = {
            r[0] for r in conn.execute("SELECT order_id FROM orders").fetchall()
        }
        expected_ids = {o[0] for o in orders}
        missing = expected_ids - saved_ids
        conn.close()
        assert not missing, f"order_ids missing after concurrent writes: {missing}"

    def test_transaction_rollback_on_integrity_failure(self, db_conn):
        """
        integrity_checked_transaction must roll back the entire batch
        when a check fails, leaving the table unchanged.

        seed_orders() calls conn.commit() internally, so we insert the
        duplicate directly inside the context manager without committing,
        letting integrity_checked_transaction own the transaction boundary.
        """
        seed_orders(db_conn, [(9000, 1, 10.0)])   # one clean row, committed
        assert_row_count(db_conn, "orders", 1)

        with pytest.raises(IntegrityError):
            with integrity_checked_transaction(db_conn):
                # Insert without committing — context manager owns commit/rollback
                db_conn.execute(
                    "INSERT INTO orders (order_id, user_id, amount) VALUES (?, ?, ?)",
                    (9000, 2, 20.0)   # duplicate order_id — triggers rollback
                )

        # Rollback must have discarded the duplicate; only the original row remains
        assert_row_count(db_conn, "orders", 1)

    def test_simultaneous_readers_dont_block_writer(self, db_path):
        """
        WAL mode: readers must not lock out a writer.
        Start 3 reader threads; writer must complete within 2 s.
        """
        setup_conn = make_connection(db_path)
        setup_conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER, user_id INTEGER, amount REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for i in range(50):
            setup_conn.execute(
                "INSERT INTO orders (order_id, user_id, amount) VALUES (?, ?, ?)",
                (i, 1, 1.0)
            )
        setup_conn.commit()
        setup_conn.close()

        stop_flag = threading.Event()

        def keep_reading():
            conn = make_connection(db_path)
            while not stop_flag.is_set():
                conn.execute("SELECT COUNT(*) FROM orders").fetchone()
            conn.close()

        readers = [threading.Thread(target=keep_reading) for _ in range(3)]
        for r in readers:
            r.start()

        import time
        start = time.perf_counter()
        writer_conn = make_connection(db_path)
        writer_conn.execute(
            "INSERT INTO orders (order_id, user_id, amount) VALUES (?, ?, ?)",
            (9999, 1, 1.0)
        )
        writer_conn.commit()
        writer_conn.close()
        elapsed = time.perf_counter() - start

        stop_flag.set()
        for r in readers:
            r.join()

        assert elapsed < 2.0, f"Writer was blocked for {elapsed:.2f}s — WAL not working"


# ══════════════════════════════════════════════
# 4. REGRESSION — guard existing test_orders_validation behavior
# ══════════════════════════════════════════════

class TestExistingBehaviorPreserved:
    """These mirror the original test_orders_validation.py but now assert on DB."""

    def test_no_duplicate_order_ids_original(self, db_conn):
        seed_orders(db_conn, [(1001, 1, 50.0), (1002, 2, 75.0)])
        duplicates = find_duplicate_order_ids(db_conn)
        assert len(duplicates) == 0

    def test_detect_duplicate_order_ids_original(self, db_conn):
        seed_orders(db_conn, [(1001, 1, 50.0), (1001, 2, 75.0), (1002, 3, 20.0)])
        duplicates = find_duplicate_order_ids(db_conn)
        assert len(duplicates) > 0
        assert duplicates[0][0] == 1001
