import requests
from framework.config import BASE_URL


class AIClient:

    def __init__(self):
        self.url = BASE_URL

    def send_prompt(self, prompt):
        response = requests.post(
            f"{self.url}/chat",
            json={"prompt": prompt},
            timeout=5
        )
        return response

    def check_health(self):
        response = requests.get(
            f"{self.url}/health",
            timeout=5
        )
        response.raise_for_status()
        return response.json()
