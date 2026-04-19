import requests
import csv
import os
from framework.config import BASE_URL


REPORT_PATH = "reports/ai_responses.csv"


class AIClient:
    def __init__(self, url=None):
        # Use provided URL or fallback to config
        self.url = url or BASE_URL

        # Ensure reports directory exists
        os.makedirs("reports", exist_ok=True)

    def _log_response(self, prompt, response):
        """
        Logs prompt and response to CSV file.
        """
        file_exists = os.path.isfile(REPORT_PATH)

        try:
            response_text = response.json()
        except Exception:
            response_text = response.text

        with open(REPORT_PATH, "a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)

            if not file_exists:
                writer.writerow(["prompt", "response", "status_code", "latency"])

            writer.writerow([
                prompt,
                response_text,
                response.status_code,
                response.elapsed.total_seconds()
            ])

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

        # Print response for debugging (visible in terminal or GitHub Actions logs)
        try:
            print("PROMPT:", prompt)
            print("RESPONSE:", response.json())
        except Exception:
            print("PROMPT:", prompt)
            print("RESPONSE:", response.text)

        # Save response to CSV
        self._log_response(prompt, response)

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
