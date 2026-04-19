from framework.api_client import AIClient

client = AIClient("http://localhost:5000/chat")

def test_api_available():

    response = client.send_prompt("Hello")
    print("LOGGING RESPONSE TO CSV")
    assert response.status_code == 200
