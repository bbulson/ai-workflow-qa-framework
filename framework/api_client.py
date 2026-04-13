import requests
from framework.config import BASE_URL

class AIClient:
    def __init__(self, base_url=None):
        # Uses the URL passed from the test, or falls back to the config default
        self.url = base_url or BASE_URL

    def send_prompt(self, prompt):
        payload = {"prompt": prompt}
        response = requests.post(
            self.url,
            json=payload,
            timeout=5
        )
        return response

    def check_health(self):
        """Returns True if the endpoint is reachable (status 200)."""
        try:
            response = requests.get(self.url, timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
