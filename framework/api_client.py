import requests
import csv
import os
import time
import logging

from framework.config import BASE_URL
from framework.test_logger import log_api_test  # ✅ moved responsibility here

ENVIRONMENT = os.getenv("TEST_ENV", "local")
REPORT_PATH = "reports/ai_responses.csv"

logging.basicConfig(level=logging.INFO)

class AIClient:
    def __init__(self, url=None):
        self.url = url or BASE_URL

        # Ensure reports directory exists
        os.makedirs("reports", exist_ok=True)

    def _log_response(self, prompt, response):
        """
        Logs prompt and response to CSV file.
        (kept separate from DB logging for lightweight reporting)
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
        """

        endpoint = self.url if self.url.endswith("/chat") else f"{self.url}/chat"
        payload = {"prompt": prompt}

        start_time = time.time()

        response = requests.post(
            endpoint,
            json=payload,
            timeout=5,
            verify=False
        )

        # delegate ALL test logging to test_logger
        log_api_test(
            test_name="api_prompt_request",
            payload=payload,
            response=response,
            start_time=start_time
        )

        # CSV logging stays here (optional layer, not DB responsibility)
        self._log_response(prompt, response)

        return response

    def check_health(self):
        """
        Checks whether the API is running.
        """

        health_url = self.url.replace("/chat", "") + "/health"

        response = requests.get(
            health_url,
            timeout=5,
            verify=False
        )

        response.raise_for_status()
        return response.json()
