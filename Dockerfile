# Playwright + Python (Chromium preinstalled). Use 1.45.0 to match the lib.
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# Install deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

ENV PYTHONUNBUFFERED=1 TZ=UTC

# Render supplies $PORT. Use shell so ${PORT:-8000} expands.
CMD ["sh", "-c", "python -m uvicorn po_svc:app --host 0.0.0.0 --port ${PORT:-8000}"]