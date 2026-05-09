import pytest
import requests_mock
from framework.api_client import AIClient
from framework.db import init_db

#def pytest_sessionstart(session):
#    init_db()

@pytest.fixture
def client():
    return AIClient("https://localhost:5000")

@pytest.fixture
def db_conn(tmp_path):
    db_file = tmp_path / "test.db"
    conn = init_db(str(db_file))

    yield conn
    conn.close()
@pytest.fixture(autouse=True)
def mock_ai_service():
    with requests_mock.Mocker() as m:

        def dynamic_response(request, context):
            data = request.json()
            prompt = data.get("prompt")

            if prompt is None:
                context.status_code = 400
                return {"error": "Prompt is null"}

            if isinstance(prompt, str) and prompt.strip() == "":
                context.status_code = 400
                return {"error": "Prompt is empty"}

            if isinstance(prompt, str) and len(prompt) > 5000:
                context.status_code = 413
                return {"error": "Payload too large"}

            context.status_code = 200
            return {"response": f"Mocked response: {prompt}"}

        m.post("https://localhost:5000/chat", json=dynamic_response)
        m.get("https://localhost:5000/health", status_code=200)

        yield m
