FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy mock server code and its HTML template
COPY mock_server/chatbot_mock.py /app/
COPY mock_server/templates /app/templates/

EXPOSE 5000

# pytest + Playwright UI tests hit this server (port 5000 via nginx)
CMD ["python", "chatbot_mock.py"]
