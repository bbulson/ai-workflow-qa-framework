import pytest
from framework.api_client import AIClient


@pytest.fixture
def client():
    """
    Provides an instance of the AIClient pointing to the local test server.
    """
    return AIClient("https://localhost:5000")
