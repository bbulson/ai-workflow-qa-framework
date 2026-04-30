from framework.api_client import AIClient

client = AIClient("http://localhost:5000")

def test_empty_prompt():

    response = client.send_prompt("")

    assert response.status_code == 400


def test_gibberish_prompt():

    response = client.send_prompt("asdkfjasldkfj")

    assert response.status_code == 200
