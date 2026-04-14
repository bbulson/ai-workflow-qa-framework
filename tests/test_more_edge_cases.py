import pytest
from framework.api_client import AIClient

# Using the client fixture from conftest.py
def test_empty_prompt(client):
    """Verify that an empty prompt returns a 400 error."""
    response = client.send_prompt("")
    assert response.status_code == 400

def test_very_long_prompt(client):
    """Verify system handles large inputs (e.g., 5000+ characters)."""
    long_prompt = "AI " * 2000 
    response = client.send_prompt(long_prompt)
    # Depending on your mock, this might be 200 or a 413 (Payload Too Large)
    assert response.status_code == 200 

def test_special_characters(client):
    """Verify handling of emojis and symbols: 🚀🔥!@#$%^&*()"""
    response = client.send_prompt("🚀 Test with Emojis and Symbols!@#$")
    assert response.status_code == 200

def test_malformed_json_logic(client):
    """
    Verify the client handles scenarios where the prompt key 
    might be missing or null (if your send_prompt method allows it).
    """
    response = client.send_prompt(None)
    assert response.status_code == 400
