from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# ── UI Route ──────────────────────────────────────────────────────
# Serves the chat frontend at the root URL.
# This is what Playwright's browser navigates to in UI tests.
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# ── API Routes ────────────────────────────────────────────────────
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "")

    if prompt is None:
        return jsonify({"error": "Prompt is null"}), 400

    if isinstance(prompt, str) and prompt.strip() == "":
        return jsonify({"error": "Prompt is empty"}), 400

    if isinstance(prompt, str) and len(prompt) > 5000:
        return jsonify({"error": "Payload too large"}), 413

    return jsonify({"response": f"Mock reply to: {prompt}"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
