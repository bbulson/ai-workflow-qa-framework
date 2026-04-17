from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/chat", methods=["POST"])
def chat():
    # force=True ignores the Content-Type header and parses JSON anyway
    # silent=True prevents the app from crashing if the body is totally empty
    data = request.get_json(force=True, silent=True)
    
    # Debug print: This will show up in your GitHub logs so we can see what arrived
    print(f"DEBUG: Received data: {data}")

    if not data or "prompt" not in data:
        return jsonify({
            "error": "Empty or invalid JSON", 
            "received": str(data)
        }), 400

    prompt = data.get("prompt")

    return jsonify({
        "status": "success",
        "response": f"Processed request: {prompt}"
    })

if __name__ == "__main__":
    # Ensure this stays 0.0.0.0 for GitHub Actions
    app.run(host='0.0.0.0', port=5000)
