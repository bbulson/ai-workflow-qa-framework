from flask import Flask, request, jsonify

app = Flask(__name__)

MAX_PROMPT_LENGTH = 50000


@app.route("/chat", methods=["POST"])
def chat():

    data = request.json
    prompt = data.get("prompt")

    if prompt is None or prompt == "":
        return jsonify({"error": "Prompt cannot be empty"}), 400

    if len(prompt) > MAX_PROMPT_LENGTH:
        return jsonify({"error": "Payload too large"}), 413

    return jsonify({
        "status": "success",
        "response": f"AI response to: {prompt}"
    }), 200


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
