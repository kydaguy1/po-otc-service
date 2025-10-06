# Use Playwright image with Chromium preinstalled
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app
COPY . .

ENV PYTHONUNBUFFERED=1 TZ=UTC

# Run service
CMD ["sh", "-c", "python -m uvicorn po_svc:app --host 0.0.0.0 --port ${PORT:-8000}"]