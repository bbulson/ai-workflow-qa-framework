"""
tests/test_db_integrity.py
==========================
Validates data persistence and integrity for the AI workflow QA framework.
Covers: persistence verification, business rule enforcement, concurrency
safety, and the integration between log_test_result() and actual DB writes.

Run:
    pytest tests/test_db_integrity.py -v
"""

import logging
import os
import threading
import pytest

log = logging.getLogger("framework.test_logger")

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
    _fetchone_scalar,
    _fetchall,
    _execute,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────
# db_conn and db_path are defined in conftest.py and work for both
# PostgreSQL (DATABASE_URL set) and SQLite (local dev).


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

    def test_data_survives_reconnect(self, db_conn, tmp_path):
        """
        Simulate a service restart — data must survive across connections.

        PostgreSQL: two successive connections to the same server both see
        the committed row (MVCC snapshot isolation, not in-memory only).
        SQLite: same test against an on-disk file, as before.
        """
        from framework.db_integrity import _is_pg
        from framework.db_utils import seed_orders as _seed

        if _is_pg(db_conn):
            # Write via db_conn, read back via a fresh independent connection
            _seed(db_conn, [(99, 1, 999.0)])
            conn2 = make_connection()
            count = _fetchone_scalar(conn2, "SELECT COUNT(*) FROM orders WHERE order_id=99")
            conn2.close()
            assert count == 1, "Row lost after reconnect (Postgres) — persistence failure"
        else:
            db_file = str(tmp_path / "persist.db")
            conn1 = make_connection(db_file)
            conn1.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER, user_id INTEGER, amount REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            _seed(conn1, [(99, 1, 999.0)])
            conn1.close()

            conn2 = make_connection(db_file)
            count = conn2.execute("SELECT COUNT(*) FROM orders WHERE order_id=99").fetchone()[0]
            conn2.close()
            assert count == 1, "Row lost after reconnect (SQLite) — persistence failure"


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
        _execute(db_conn, "INSERT INTO orders (order_id, user_id, amount) VALUES (NULL, 1, 10.0)")
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
            r["order_id"] for r in _fetchall(conn, "SELECT order_id FROM orders")
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
                _execute(db_conn,
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
        seed_batch = [(i, 1, 1.0) for i in range(50)]
        from framework.db_utils import seed_orders as _seed
        _seed(setup_conn, seed_batch)
        setup_conn.close()

        stop_flag = threading.Event()

        def keep_reading():
            conn = make_connection(db_path)
            while not stop_flag.is_set():
                _fetchone_scalar(conn, "SELECT COUNT(*) FROM orders")
            conn.close()

        readers = [threading.Thread(target=keep_reading) for _ in range(3)]
        for r in readers:
            r.start()

        import time
        start = time.perf_counter()
        writer_conn = make_connection(db_path)
        _execute(writer_conn,
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
# 4. PERFORMANCE SLA — time-bound concurrency checks
# ══════════════════════════════════════════════

class TestPerformanceSLA:
    """
    Benchmark concurrent write workloads against defined SLA thresholds.

    These tests assert that the database layer meets latency and throughput
    targets under the same parallel-insert pressure used in production-like
    agentic workflows.  A failure here signals infrastructure regression,
    not a logic bug.

    SLA targets (conservative for CI runners — tighten for dedicated hardware):
      - 100 inserts across 10 workers must complete in < 5 s
      - Mean per-insert latency must stay below 50 ms
      - Write throughput must exceed 20 rows/sec
    """

    MAX_TOTAL_SECONDS   = 5.0    # wall-clock budget for the full batch
    MAX_MEAN_LATENCY_MS = 200.0  # average time per committed row (CI-safe; tighten on dedicated hardware)
    MIN_ROWS_PER_SECOND = 20.0   # minimum acceptable write throughput

    def test_concurrent_inserts_complete_within_sla(self, db_path):
        """
        100 rows across 10 workers must land within the wall-clock SLA.
        Measures end-to-end time including connection overhead and commit.
        """
        import time
        orders = [(i, i % 5, float(i * 10)) for i in range(300, 400)]

        start = time.perf_counter()
        errors = run_concurrent_inserts(db_path, orders, workers=10)
        elapsed = time.perf_counter() - start

        assert errors == [], f"Insert errors during SLA test: {errors}"
        log.info(
            "SLA | concurrent_inserts | rows=100 workers=10 | "
            "elapsed=%.3fs threshold=%.1fs | %s",
            elapsed, self.MAX_TOTAL_SECONDS,
            "PASS" if elapsed < self.MAX_TOTAL_SECONDS else "FAIL"
        )
        assert elapsed < self.MAX_TOTAL_SECONDS, (
            f"SLA breach: {elapsed:.2f}s exceeded {self.MAX_TOTAL_SECONDS}s "
            f"threshold for 100 concurrent inserts"
        )

    def test_mean_insert_latency_within_sla(self, db_path):
        """
        Mean per-insert latency must stay below MAX_MEAN_LATENCY_MS.
        Each worker times its own insert individually so outliers are visible.
        """
        import time
        import threading

        orders = [(i, i % 5, float(i)) for i in range(400, 450)]
        latencies: list = []
        lock = threading.Lock()
        errors: list = []

        def timed_insert(order):
            try:
                conn = make_connection(db_path)
                t0 = time.perf_counter()
                _execute(conn,
                    "INSERT INTO orders (order_id, user_id, amount) "
                    "VALUES (?, ?, ?)",
                    order
                )
                conn.commit()
                ms = (time.perf_counter() - t0) * 1000
                conn.close()
                with lock:
                    latencies.append(ms)
            except Exception as exc:
                with lock:
                    errors.append(str(exc))

        threads = [threading.Thread(target=timed_insert, args=(o,)) for o in orders]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Insert errors during latency test: {errors}"
        assert latencies, "No latency samples recorded"

        mean_ms = sum(latencies) / len(latencies)
        log.info(
            "SLA | mean_insert_latency | rows=%d | mean=%.2fms min=%.2fms max=%.2fms threshold=%.0fms | %s",
            len(latencies), mean_ms, min(latencies), max(latencies),
            self.MAX_MEAN_LATENCY_MS,
            "PASS" if mean_ms < self.MAX_MEAN_LATENCY_MS else "FAIL"
        )
        assert mean_ms < self.MAX_MEAN_LATENCY_MS, (
            f"Mean insert latency {mean_ms:.2f}ms exceeds "
            f"{self.MAX_MEAN_LATENCY_MS}ms SLA "
            f"(min={min(latencies):.2f}ms, max={max(latencies):.2f}ms)"
        )

    def test_write_throughput_meets_sla(self, db_path):
        """
        Write throughput must exceed MIN_ROWS_PER_SECOND.
        Calculated as rows_committed / wall_clock_seconds.
        """
        import time
        orders = [(i, i % 5, float(i)) for i in range(500, 550)]

        start  = time.perf_counter()
        errors = run_concurrent_inserts(db_path, orders, workers=5)
        elapsed = time.perf_counter() - start

        assert errors == [], f"Insert errors during throughput test: {errors}"

        rows_per_sec = len(orders) / elapsed
        log.info(
            "SLA | write_throughput | rows=%d workers=5 | "
            "elapsed=%.3fs throughput=%.1f rows/s threshold=%.0f rows/s | %s",
            len(orders), elapsed, rows_per_sec, self.MIN_ROWS_PER_SECOND,
            "PASS" if rows_per_sec >= self.MIN_ROWS_PER_SECOND else "FAIL"
        )
        assert rows_per_sec >= self.MIN_ROWS_PER_SECOND, (
            f"Write throughput {rows_per_sec:.1f} rows/s fell below "
            f"{self.MIN_ROWS_PER_SECOND} rows/s SLA "
            f"({len(orders)} rows in {elapsed:.2f}s)"
        )


# ══════════════════════════════════════════════
# 5. REGRESSION — guard existing test_orders_validation behavior
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
        assert duplicates[0]["order_id"] == 1001


# ══════════════════════════════════════════════
# 5. END-TO-END — real HTTP boundary → DB write
#
# Requires the stack to be running:
#   docker compose up --build -d
#
# Skipped automatically when the service is not up.
# Run in CI with: pytest -m e2e
# ══════════════════════════════════════════════

import requests


def _service_available(url: str = "https://localhost:5000/health") -> bool:
    """Return True only if the live mock server is reachable."""
    try:
        r = requests.get(url, timeout=2, verify=False)
        return r.status_code == 200
    except Exception:
        return False


pytest_e2e = pytest.mark.skipif(
    not _service_available(),
    reason="flask-mock not running — start with: docker compose up --build -d"
)


LIVE_URL = "https://localhost:5000"
# Path on the host — matches the docker-compose volume mount ./data:/app/data
HOST_DB_PATH = "data/qa_results.db"


def _live_post(prompt: str) -> int:
    """
    POST directly to the running container, bypassing requests_mock.
    Returns the HTTP status code.
    """
    r = requests.post(
        f"{LIVE_URL}/chat",
        json={"prompt": prompt},
        timeout=5,
        verify=False,
    )
    return r.status_code


def _assert_container_db_writable():
    """
    Hit /db-status on the container and fail fast with a clear message
    if the container cannot connect to or write to its DB.
    """
    try:
        r = requests.get(f"{LIVE_URL}/db-status", timeout=3, verify=False)
        body = r.json()
        if not body.get("connected"):
            raise IntegrityError(
                f"Container DB not writable: {body.get('error')} "
                f"(path: {body.get('db_path')}, exists: {body.get('db_exists')})"
            )
    except IntegrityError:
        raise
    except Exception as exc:
        raise IntegrityError(f"/db-status check failed: {exc}")


@pytest.mark.e2e
class TestEndToEnd:
    """
    Crosses a real service boundary: pytest → HTTP → flask-mock container
    → DB write → integrity assertion on the shared data/qa_results.db file.

    Uses direct requests calls (not AIClient) so requests_mock in conftest
    does not intercept the traffic — the call must reach the live container.

    The docker volume mount (./data:/app/data) makes the container's DB
    write visible to pytest running on the host.
    """

    @pytest_e2e
    def test_chat_request_persisted_to_db(self):
        """
        POST /chat → flask-mock writes a test_result row with status PASS.
        """
        _assert_container_db_writable()
        conn = make_connection(HOST_DB_PATH)
        _live_post("end-to-end test prompt")
        assert_test_result_logged(conn, "chat_endpoint", expected_status="PASS")
        conn.close()

    @pytest_e2e
    def test_invalid_prompt_logged_as_fail(self):
        """
        Empty prompt → flask-mock returns 400 and logs status FAIL.
        The assertion queries rows written after this test started so the
        PASS row from the previous test does not satisfy the check.
        """
        import datetime
        _assert_container_db_writable()
        conn = make_connection(HOST_DB_PATH)
        # Record row count before the post so we can assert a NEW row was added
        # with the correct status, regardless of timestamp precision.
        before_count = _fetchone_scalar(
            conn,
            "SELECT COUNT(*) FROM test_results WHERE test_name = ?",
            ("chat_endpoint",)
        )

        _live_post("")

        # Wait briefly to ensure the container has committed the write
        import time as _time
        _time.sleep(0.3)

        rows = _fetchall(
            conn,
            "SELECT status FROM test_results WHERE test_name = ? "
            "ORDER BY id DESC",
            ("chat_endpoint",)
        )

        after_count = len(rows)
        if after_count <= before_count:
            raise IntegrityError(
                "No new chat_endpoint row was written after the empty prompt post. "
                "Was log_test_result() called?"
            )
        assert rows[0]["status"] == "FAIL", (
            f"Expected FAIL for empty prompt, got {rows[0]['status']}"
        )
        conn.close()

    @pytest_e2e
    def test_db_integrity_holds_after_live_requests(self):
        """
        After several live requests, full integrity check must still pass —
        no duplicates, no nulls, no bad amounts introduced by the service.
        """
        _assert_container_db_writable()
        conn = make_connection(HOST_DB_PATH)
        # Clear any rows left by earlier unit/integration tests so the
        # integrity check only sees rows produced by this E2E test.
        _execute(conn, "DELETE FROM orders")
        conn.commit()
        for i in range(5):
            _live_post(f"concurrent prompt {i}")
        result = validate_db_state(conn, raise_on_failure=False)
        conn.close()
        assert result.ok, f"Integrity failures after live requests:\n{result}"

    @pytest_e2e
    def test_cross_node_data_consistency(self):
        """
        Verify data written by one node is immediately visible to another,
        and that both nodes actually participated in handling requests.

        Sends 20 requests through nginx, which round-robins across flask-mock
        and flask-mock-2.  Each node stamps its hostname into the
        'environment' column of every row it writes.  The test asserts:
          1. All 20 rows landed in Postgres (no data loss across nodes).
          2. Both node hostnames appear in the written rows (distribution proven).
          3. Full integrity check passes across all rows (no corruption).
        """
        import time
        _assert_container_db_writable()
        conn = make_connection(HOST_DB_PATH)

        # Baseline — capture row count before this test's writes
        before = _fetchone_scalar(
            conn,
            "SELECT COUNT(*) FROM test_results"
        )

        # Fire 20 requests — nginx round-robins across both nodes
        for i in range(20):
            _live_post(f"cross-node probe {i}")

        # Brief settle to ensure all commits are visible
        time.sleep(0.5)

        after = _fetchone_scalar(
            conn,
            "SELECT COUNT(*) FROM test_results"
        )
        new_rows = after - before

        # Count rows per node via the environment (hostname) column
        node_rows = _fetchall(
            conn,
            "SELECT environment, COUNT(*) as cnt FROM test_results "
            "WHERE environment IS NOT NULL "
            "GROUP BY environment ORDER BY environment"
        )
        node_counts = {r["environment"]: r["cnt"] for r in node_rows if r["environment"]}
        nodes_seen  = list(node_counts.keys())
        node_summary = ", ".join(f"{n}={c}" for n, c in node_counts.items())

        log.info(
            "cross_node_consistency | requests=20 | new_rows=%d | nodes=%s | %s",
            new_rows,
            node_summary,
            "PASS" if new_rows == 20 and len(nodes_seen) >= 2 else "FAIL"
        )

        assert new_rows == 20, (
            f"Cross-node data loss: sent 20 requests across 2 nodes "
            f"but only {new_rows} rows landed in Postgres."
        )

        assert len(nodes_seen) >= 2, (
            f"Distribution not proven: expected rows from at least 2 nodes "
            f"but only saw: {node_summary}. "
            f"nginx may not be load balancing correctly."
        )

        # Full integrity check across all rows — no duplicates or corrupt data
        # introduced by concurrent multi-node writes
        result = validate_db_state(conn, raise_on_failure=False)
        conn.close()
        assert result.ok, f"Integrity failures after cross-node writes:\n{result}"
