FROM python:3.10-slim

WORKDIR /app

# Prevent Python from writing pyc files and enable real-time logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy mock server code
COPY mock_server/chatbot_mock.py /app/

# Expose Flask port
EXPOSE 5000

# Run the app
CMD ["python", "chatbot_mock.py"]
