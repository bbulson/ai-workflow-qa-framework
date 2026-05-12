import time
import os
from framework.db import log_test_result
import logging
logger = logging.getLogger(__name__)

ENVIRONMENT = os.getenv("TEST_ENV", "local")

def log_api_test(test_name, payload, response, start_time):

    latency_ms = (time.time() - start_time) * 1000

    try:
        response_json = response.json()
    except Exception:
        response_json = {"raw": response.text}

    status = "PASS" if response.status_code == 200 else "FAIL"

    log_test_result(
        test_name=test_name,
        status=status,
        latency_ms=latency_ms,
        request_payload=payload,
        response_payload=response_json,
        response_code=response.status_code,
        environment=ENVIRONMENT
    )
    logger.info(
    f"{test_name} | {status} | {response.status_code} | {latency_ms:.2f}ms\n"
    f"Request: {payload}\n"
    f"Response: {response_json}"
    )
