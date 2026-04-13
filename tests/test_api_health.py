from framework.api_client import AIClient

client = AIClient("https://api.example.com/chat")

def test_api_available():

    response = client.send_prompt("Hello")

    assert response.status_code == 200
