import sqlite3
import os
import json

#DB_PATH = "data/qa_results.db"

def init_db(db_path="data/qa_results.db"):
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(db_path)
    #conn = sqlite3.connect(DB_PATH)
    #cursor = conn.cursor()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        user_id INTEGER,
        amount REAL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_name TEXT,
            status TEXT,
            latency_ms REAL,
            request_payload TEXT,
            response_payload TEXT,
            response_code INTEGER,
            environment TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    #conn.close()
    return conn


def log_test_result(conn=None, test_name=None, status=None, latency_ms=None,
                    request_payload=None, response_payload=None,
                    response_code=None, environment=None):

    should_close = False

    if conn is None:
        #ensure DB + tables exist
        conn = init_db("data/qa_results.db")
        should_close = True

    #conn = sqlite3.connect(DB_PATH)
    #conn = sqlite3.connect(db_path)
    #cursor = conn.cursor()

    conn.execute("""
        INSERT INTO test_results (
            test_name, status, latency_ms,
            request_payload, response_payload,
            response_code, environment
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        test_name,
        status,
        latency_ms,
        json.dumps(request_payload),
        json.dumps(response_payload),
        response_code,
        environment
    ))

    conn.commit()
    #conn.close()
    if should_close:
        conn.close()
