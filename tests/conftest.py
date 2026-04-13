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
    """
    Automatically mocks all API calls during tests.
    'autouse=True' means you don't even have to add it to your test arguments.
    """
    with requests_mock.Mocker() as m:
        # This intercepts the POST request your client is making
        m.post("https://api.example.com/chat", 
               json={"status": "success", "response": "This is a mocked AI response"}, 
               status_code=200)
        
        # This intercepts the GET request for your health check
        m.get("https://api.example.com/chat", 
              status_code=200)
        
        yield m
