import pytest
from framework.api_client import AIClient

@pytest.fixture
def client():
    return AIClient()
