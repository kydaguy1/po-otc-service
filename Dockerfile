# Playwright + Python base with Chromium that matches 1.45.0
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app
COPY . .

ENV PYTHONUNBUFFERED=1 TZ=UTC

# Render will set $PORT; pass it to uvicorn via shell form so it expands
CMD ["sh","-c","python -m uvicorn po_svc:app --host 0.0.0.0 --port ${PORT:-8000}"]