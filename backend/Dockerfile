FROM python:3.11-slim

WORKDIR /app

# System deps for yfinance / curl_cffi
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY app ./app

ENV APP_ENV=production
ENV DEBUG=false
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
