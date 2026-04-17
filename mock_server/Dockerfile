FROM python:3.10-slim

WORKDIR /app

# Reach out to the root folder to get the requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Reach into the mock_server folder for the script
COPY mock_server/chatbot_mock.py .

# Run the app
CMD ["python", "chatbot_mock.py"]
