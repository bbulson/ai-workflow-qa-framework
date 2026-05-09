import logging
from framework.api_client import AIClient
import os

client = AIClient()

def test_api_available(client): 
    #print("DB PATH:", os.path.abspath("qa_results.db"))
    response = client.send_prompt("Hello")
    #print("LOGGING RESPONSE TO CSV")
    #print("Logging test result to SQLite database")
    logging.info("Logging API test result to database")
    assert response.status_code == 200
