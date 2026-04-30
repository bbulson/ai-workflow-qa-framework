from flask import Flask, request, jsonify

app = Flask(__name__)

# limit request size (1 MB)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()

    if not data or "prompt" not in data:
        return jsonify({"error": "Bad Request"}), 400

    prompt = data["prompt"]

    if not prompt:
        return jsonify({"error": "Prompt cannot be empty"}), 400

    return jsonify({"response": "Mock AI response"}), 200


if __name__ == "__main__":
    app.run(port=5000)
