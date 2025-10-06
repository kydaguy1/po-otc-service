# Playwright + Python (Chromium preinstalled)
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# install python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy app
COPY . .

ENV PYTHONUNBUFFERED=1 TZ=UTC

# IMPORTANT: use shell form so ${PORT} from Render expands
CMD ["sh","-c","python -m uvicorn po_svc:app --host 0.0.0.0 --port ${PORT:-8000}"]