"""
order_service/order_service.py
==============================
Order Processing Microservice.

Receives order events triggered by chat sessions and persists them to a
dedicated orders database (separate schema/DB from the chatbot service).
This intentional separation is what makes cross-service SQL validation
meaningful — two independent services, two data stores, one integrity check.

Endpoints:
  POST /orders          — create an order linked to a chat session
  GET  /orders/<id>     — retrieve a single order
  GET  /orders          — list all orders (for validation queries)
  GET  /health          — liveness probe
"""

import os
import time
import socket
from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras

app = Flask(__name__)

NODE_ID = socket.gethostname()

ORDER_DB_URL = os.environ.get(
    "ORDER_DB_URL",
    "postgresql://qauser:qapassword@db:5432/orderdb"
)

_conn = None


def get_conn():
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(
            ORDER_DB_URL,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        _conn.autocommit = False
        _init_schema(_conn)
    return _conn


def _init_schema(conn):
    """Create orders table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id             SERIAL PRIMARY KEY,
                session_id     TEXT        NOT NULL,
                user_id        INTEGER     NOT NULL,
                product        TEXT        NOT NULL,
                amount         NUMERIC     NOT NULL,
                status         TEXT        NOT NULL DEFAULT 'pending',
                source_node    TEXT,
                created_at     TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    conn.commit()


# ── Routes ────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "order-service", "node": NODE_ID})


@app.route("/orders", methods=["POST"])
def create_order():
    """
    Create an order linked to a chat session.

    Expected JSON body:
      {
        "session_id": "abc123",   -- must match a session in the chat service
        "user_id":    42,
        "product":    "widget",
        "amount":     19.99
      }
    """
    data = request.get_json(silent=True) or {}

    session_id = data.get("session_id")
    user_id    = data.get("user_id")
    product    = data.get("product")
    amount     = data.get("amount")

    # Basic validation
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    if user_id is None:
        return jsonify({"error": "user_id is required"}), 400
    if not product:
        return jsonify({"error": "product is required"}), 400
    if amount is None or float(amount) <= 0:
        return jsonify({"error": "amount must be a positive number"}), 400

    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (session_id, user_id, product, amount, source_node)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, session_id, user_id, product, amount, status, created_at
                """,
                (session_id, user_id, product, float(amount), NODE_ID)
            )
            row = cur.fetchone()
        conn.commit()
        return jsonify(dict(row)), 201

    except Exception as exc:
        app.logger.error("Order creation failed: %s", exc)
        return jsonify({"error": "internal server error"}), 500


@app.route("/orders/<int:order_id>", methods=["GET"])
def get_order(order_id):
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
            row = cur.fetchone()
        if row is None:
            return jsonify({"error": "order not found"}), 404
        return jsonify(dict(row))
    except Exception as exc:
        app.logger.error("Order fetch failed: %s", exc)
        return jsonify({"error": "internal server error"}), 500


@app.route("/orders", methods=["GET"])
def list_orders():
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orders ORDER BY created_at DESC")
            rows = cur.fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as exc:
        app.logger.error("Order list failed: %s", exc)
        return jsonify({"error": "internal server error"}), 500


@app.route("/orders/reset", methods=["POST"])
def reset_orders():
    """Test-only endpoint — clears all orders for a clean test run."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM orders")
        conn.commit()
        return jsonify({"deleted": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
