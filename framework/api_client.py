import requests
from framework.config import BASE_URL

class AIClient:

    def send_prompt(self, prompt):

        payload = {"prompt": prompt}

        response = requests.post(
            BASE_URL,
            json=payload,
            timeout=5
        )

        return response
