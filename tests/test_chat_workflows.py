import json

def test_chat_workflows(client):

    with open("test_data/prompts.json") as f:
        prompts = json.load(f)

    for prompt in prompts:

        response = client.send_prompt(prompt)

        assert response.status_code == 200
        assert len(response.json()["response"]) > 0
