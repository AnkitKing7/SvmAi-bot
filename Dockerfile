FROM python:3.12-slim

LABEL maintainer="AnkitCoder"
LABEL description="SVM AI — Autonomous Discord AI Agent"

WORKDIR /app

# System deps for common optional tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

COPY bot.py .
COPY .env.example .

RUN mkdir -p /app/data /app/workspace /app/logs

ENV PYTHONUNBUFFERED=1 \
    WORKSPACE_DIR=/app/workspace \
    DATA_DIR=/app/data \
    LOG_DIR=/app/logs \
    LOCALAI_URL=http://127.0.0.1:8080

# No ports exposed — Discord outbound only
VOLUME ["/app/data", "/app/workspace", "/app/logs"]

CMD ["python", "bot.py"]
