import os
import socket
import time
from flask import Flask, request, jsonify, render_template
from framework.db import init_db, log_test_result
from framework.db_integrity import _fetchone_scalar

app = Flask(__name__)

# Each container gets a unique hostname from Docker (service name or ID).
# Stored on every DB row so tests can verify which node handled each write.
NODE_ID = socket.gethostname()

# Use an absolute path so the DB location is unambiguous regardless of
# the working directory Flask starts from inside the container.
DB_PATH = os.environ.get("QA_DB_PATH", "/app/data/qa_results.db")

_conn = None
_conn_error = None


def get_conn():
    global _conn, _conn_error
    if _conn is None:
        try:
            _conn = init_db(DB_PATH)
            _conn_error = None
        except Exception as exc:
            _conn_error = str(exc)
            raise
    return _conn


# ── UI Route ──────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


# ── API Routes ────────────────────────────────────────────────────
@app.route("/chat", methods=["POST"])
def chat():
    start = time.perf_counter()
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "")

    if prompt is None:
        response, code = {"error": "Prompt is null"}, 400
    elif isinstance(prompt, str) and prompt.strip() == "":
        response, code = {"error": "Prompt is empty"}, 400
    elif isinstance(prompt, str) and len(prompt) > 5000:
        response, code = {"error": "Payload too large"}, 413
    else:
        response, code = {"response": f"Mock reply to: {prompt}"}, 200

    latency_ms = (time.perf_counter() - start) * 1000
    status = "PASS" if code == 200 else "FAIL"

    try:
        log_test_result(
            conn=get_conn(),
            test_name="chat_endpoint",
            status=status,
            latency_ms=round(latency_ms, 3),
            request_payload=data,
            response_payload=response,
            response_code=code,
            environment=NODE_ID,
        )
    except Exception as exc:
        app.logger.warning("DB log failed (non-fatal): %s", exc)

    return jsonify(response), code


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/db-status", methods=["GET"])
def db_status():
    """Debug endpoint — confirms DB path and connection state."""
    try:
        conn = get_conn()
        row_count = _fetchone_scalar(conn, "SELECT COUNT(*) FROM test_results")
        return jsonify({
            "db_path": DB_PATH,
            "db_exists": os.path.exists(DB_PATH),
            "connected": True,
            "test_results_count": row_count,
            "error": None,
        })
    except Exception as exc:
        return jsonify({
            "db_path": DB_PATH,
            "db_exists": os.path.exists(DB_PATH),
            "connected": False,
            "error": str(exc),
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
