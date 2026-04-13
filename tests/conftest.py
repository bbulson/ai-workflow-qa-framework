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
            # If the JSON body has an empty prompt, return 400
            if request.json().get("prompt") == "":
                context.status_code = 400
                return {"error": "Empty prompt"}
            # Otherwise return 200
            context.status_code = 200
            return {"status": "success", "response": "Mock Response"}

        m.post("https://api.example.com/chat", json=dynamic_response)
        m.get("https://api.example.com/chat", status_code=200)
        yield m
