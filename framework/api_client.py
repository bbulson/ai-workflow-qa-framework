import requests
from framework.config import BASE_URL


class AIClient:
    def __init__(self, url=None):
        # Use provided URL or fallback to config
        self.url = url or BASE_URL

    def send_prompt(self, prompt):
        """
        Sends a prompt to the chatbot API and returns the response object.
        Handles cases where the base URL may already include /chat.
        """

        endpoint = self.url if self.url.endswith("/chat") else f"{self.url}/chat"

        response = requests.post(
            endpoint,
            json={"prompt": prompt},
            timeout=5
        )

        return response

    def check_health(self):
        """
        Checks whether the API is running by calling the health endpoint.
        """

        health_url = self.url.replace("/chat", "") + "/health"

        response = requests.get(
            health_url,
            timeout=5
        )

        response.raise_for_status()
        return response.json()
