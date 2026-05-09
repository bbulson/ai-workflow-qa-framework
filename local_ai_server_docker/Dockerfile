FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# The realistic AI server - higher token limit, status field in response
# JMeter load tests target this server (port 5001 via nginx-jmeter)
COPY local_ai_server.py /app/

EXPOSE 5001

CMD ["python", "local_ai_server.py"]
