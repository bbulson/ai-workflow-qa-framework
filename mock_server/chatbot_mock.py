from flask import Flask, request, jsonify

app = Flask(__name__)

MAX_PROMPT_LENGTH = 5000


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt")

    # Null / missing prompt field
    if prompt is None:
        return jsonify({"error": "Prompt is null"}), 400

    # Wrong type (numbers, booleans, objects, arrays, etc.)
    if not isinstance(prompt, str):
        return jsonify({"error": "Prompt must be a string"}), 400

    # Empty or whitespace-only
    if prompt.strip() == "":
        return jsonify({"error": "Prompt is empty"}), 400

    # Oversized payload (length is Unicode code points, not bytes)
    if len(prompt) > MAX_PROMPT_LENGTH:
        return jsonify({"error": "Payload too large"}), 413

    return jsonify({"response": f"Mock reply to: {prompt}"})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
