def dynamic_response(request, context):
    data = request.json()
    prompt = data.get("prompt")

    # -----------------------
    # VALIDATION RULES
    # -----------------------

    # None or missing
    if prompt is None:
        context.status_code = 400
        return {"error": "Prompt cannot be null"}

    # Empty string
    if isinstance(prompt, str) and prompt.strip() == "":
        context.status_code = 400
        return {"error": "Prompt cannot be empty"}

    # Very large payload
    if isinstance(prompt, str) and len(prompt) > 5000:
        context.status_code = 413
        return {"error": "Payload too large"}

    # Default success
    context.status_code = 200
    return {
        "status": "success",
        "response": f"Mocked response for: {prompt}"
    }
