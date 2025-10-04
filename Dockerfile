# Dockerfile (for po-otc-ky)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget gnupg ca-certificates fonts-liberation libasound2 \
    libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 libdrm2 \
    libgbm1 libgtk-3-0 libnspr4 libnss3 libx11-6 libxcomposite1 \
    libxdamage1 libxfixes3 libxkbcommon0 libxrandr2 xdg-utils \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# IMPORTANT: install browsers *after* python package is present
# Use module form so it works even if shell can't find "playwright"
RUN python -m playwright install --with-deps chromium

# Copy the rest
COPY . .

# Render injects PORT. We bind to it.
ENV HOST=0.0.0.0
CMD uvicorn po_api:app --host 0.0.0.0 --port $PORT
