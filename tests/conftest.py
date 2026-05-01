import pytest
import requests_mock
from pathlib import Path

from framework.api_client import AIClient

MAX_PROMPT_LENGTH = 5000

# HTML report ordering follows execution order — run legacy tests first so their
# stdout/logs (e.g. from AIClient) appear toward the beginning of the report.
_TEST_MODULE_ORDER = [
    "test_api_health.py",
    "test_chat_workflows.py",
    "test_edge_cases.py",
    "test_more_edge_cases.py",
    "test_chat_contract_flask.py",
    "test_chat_contract_mocked.py",
    "test_api_client_resilience.py",
]


def pytest_collection_modifyitems(config, items):
    rank = {name: idx for idx, name in enumerate(_TEST_MODULE_ORDER)}
    fallback = len(_TEST_MODULE_ORDER)

    def sort_key(it):
        mod_name = Path(getattr(it, "path", it.fspath)).name
        line = (
            it.location[1]
            if it.location and it.location[1] is not None
            else 0
        )
        return (rank.get(mod_name, fallback), line, it.nodeid)

    items.sort(key=sort_key)


@pytest.fixture
def client():
    return AIClient("https://localhost:5000")


@pytest.fixture(autouse=True)
def mock_ai_service():
    with requests_mock.Mocker() as m:

        def dynamic_response(request, context):
            # Mirror Flask: invalid/missing JSON body -> {} -> prompt None
            try:
                data = request.json()
            except (ValueError, TypeError):
                data = {}
            if data is None:
                data = {}
            prompt = data.get("prompt")

            if prompt is None:
                context.status_code = 400
                return {"error": "Prompt is null"}

            if not isinstance(prompt, str):
                context.status_code = 400
                return {"error": "Prompt must be a string"}

            if prompt.strip() == "":
                context.status_code = 400
                return {"error": "Prompt is empty"}

            if len(prompt) > MAX_PROMPT_LENGTH:
                context.status_code = 413
                return {"error": "Payload too large"}

            context.status_code = 200
            return {"response": f"Mocked response: {prompt}"}

        m.post("https://localhost:5000/chat", json=dynamic_response)
        m.get("https://localhost:5000/health", json={"status": "ok"}, status_code=200)

        yield m
