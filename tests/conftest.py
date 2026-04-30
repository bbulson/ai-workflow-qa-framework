import pytest
import subprocess
import time
from framework.api_client import AIClient


@pytest.fixture(scope="session", autouse=True)
def start_local_server():
    """
    Starts the local AI test server before tests run
    and shuts it down afterward.
    """
    process = subprocess.Popen(["python", "local_ai_server.py"])

    # give server time to start
    time.sleep(2)

    yield

    process.terminate()


@pytest.fixture
def client():
    """
    Provides an instance of the AIClient pointing to localhost.
    """
    return AIClient("http://localhost:5000")
