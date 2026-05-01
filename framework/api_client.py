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

    @staticmethod
    def _safe_text(value):
        """
        Return a console-safe representation for Windows cp1252 terminals.
        Preserves readability while avoiding UnicodeEncodeError on emoji.
        """
        text = str(value)
        return text.encode("ascii", "backslashreplace").decode("ascii")

    def send_prompt(self, prompt):
        """
        Sends a prompt to the chatbot API and returns the response object.
        Handles cases where the base URL may already include /chat.
        """

        endpoint = self.url if self.url.endswith("/chat") else f"{self.url}/chat"

        response = requests.post(
            endpoint,
            json={"prompt": prompt},
            timeout=5,
            verify=False   # <-- important for CI self-signed certs
        )

        # Print response for debugging (visible in terminal or GitHub Actions logs)
        try:
            print("PROMPT:", self._safe_text(prompt))
            print("RESPONSE:", self._safe_text(response.json()))
        except Exception:
            print("PROMPT:", self._safe_text(prompt))
            print("RESPONSE:", self._safe_text(response.text))

        # Save response to CSV
        self._log_response(prompt, response)

        return response

    def send_chat_payload(self, payload):
        """
        POST /chat with an arbitrary JSON object (contract tests: missing key,
        wrong types, extra fields).
        """
        endpoint = self.url if self.url.endswith("/chat") else f"{self.url}/chat"
        response = requests.post(
            endpoint,
            json=payload,
            timeout=5,
            verify=False,
        )
        try:
            print("PAYLOAD:", self._safe_text(payload))
            print("RESPONSE:", self._safe_text(response.json()))
        except Exception:
            print("PAYLOAD:", self._safe_text(payload))
            print("RESPONSE:", self._safe_text(response.text))
        self._log_response(repr(payload), response)
        return response

    def send_chat_raw(self, body, content_type="application/json"):
        """
        POST /chat with a raw body string (malformed JSON, wrong Content-Type).
        """
        endpoint = self.url if self.url.endswith("/chat") else f"{self.url}/chat"
        headers = {"Content-Type": content_type}
        response = requests.post(
            endpoint,
            data=body,
            headers=headers,
            timeout=5,
            verify=False,
        )
        try:
            print("RAW BODY:", self._safe_text(body[:200] if body else body))
            print("RESPONSE:", self._safe_text(response.json()))
        except Exception:
            print("RAW BODY:", self._safe_text(body[:200] if body else body))
            print("RESPONSE:", self._safe_text(response.text))
        self._log_response(body, response)
        return response

    def check_health(self):
        """
        Checks whether the API is running by calling the health endpoint.
        """

        health_url = self.url.replace("/chat", "") + "/health"

        response = requests.get(
            health_url,
            timeout=5,
            verify=False
        )

        response.raise_for_status()
        return response.json()
