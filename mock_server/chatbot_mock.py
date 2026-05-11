import time
from flask import Flask, request, jsonify, render_template
from framework.db import init_db, log_test_result

app = Flask(__name__)

# DB connection is initialised lazily on first request rather than at
# module load time. This prevents a missing or unwritable data/ directory
# from crashing the Flask process before it can serve any requests.
_conn = None

def get_conn():
    global _conn
    if _conn is None:
        _conn = init_db("data/qa_results.db")
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

    # DB write is best-effort — a logging failure must never affect the
    # HTTP response that tests are asserting on.
    try:
        log_test_result(
            conn=get_conn(),
            test_name="chat_endpoint",
            status=status,
            latency_ms=round(latency_ms, 3),
            request_payload=data,
            response_payload=response,
            response_code=code,
            environment="docker",
        )
    except Exception as exc:
        app.logger.warning("DB log failed (non-fatal): %s", exc)

    return jsonify(response), code


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
