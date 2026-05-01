"""
API health / smoke tests.

Previously used a module-level AIClient() that bypassed the mock fixture.
Now uses the `client` fixture so tests are fully isolated.
"""


def test_api_available(client):
    response = client.send_prompt("Hello")
    assert response.status_code == 200


def test_health_endpoint(client):
    """Health check endpoint should return 200."""
    response = client.check_health()
    assert response["status"] == "ok"
