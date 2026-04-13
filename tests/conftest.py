import pytest
import requests_mock
from framework.api_client import AIClient

@pytest.fixture
def client():
    """Provides an instance of the AIClient to tests."""
    # We pass a URL because your tests are expecting to initialize with one
    return AIClient("https://api.example.com/chat")
@pytest.fixture(autouse=True)
def mock_ai_service():
    with requests_mock.Mocker() as m:
        def dynamic_response(request, context):
            # Parse the JSON body sent by the AIClient
            data = request.json()
            prompt = data.get("prompt", "")

            if prompt == "":
                context.status_code = 400
                return {"error": "Bad Request", "message": "Prompt cannot be empty"}
            
            # Default successful response
            context.status_code = 200
            return {
                "status": "success", 
                "response": f"Mocked response for: {prompt}"
            }

        # Register the callback for POST requests
        m.post("https://api.example.com/chat", json=dynamic_response)
        
        # Keep a simple 200 for the health check GET request
        m.get("https://api.example.com/chat", status_code=200)
        
        yield m
