from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/chat", methods=["POST"])
def chat():

    prompt = request.json.get("prompt")

    if not prompt:
        return jsonify({"error": "Empty prompt"}), 400

    return jsonify({
        "response": f"Processed request: {prompt}"
    })

if __name__ == "__main__":
    app.run(port=5000)
