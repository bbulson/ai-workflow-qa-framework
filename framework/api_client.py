import requests
from framework.config import BASE_URL

class AIClient:
    def __init__(self, base_url=None):
        # Uses the URL passed from the test, or falls back to the config default
        self.url = base_url or BASE_URL

def send_prompt(self, prompt):
    response = requests.post(
        f"{self.url}/chat",
        json={"prompt": prompt},
        timeout=5
    )
    response.raise_for_status()
    return response.json()

def check_health(self):
    response = requests.get(
        f"{self.url}/health",
        timeout=5
    )
    response.raise_for_status()
    return response.json()
