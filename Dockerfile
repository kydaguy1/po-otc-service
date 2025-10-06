# Use the Playwright base image (Chromium preinstalled)
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

# install deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy app
COPY . .

ENV PYTHONUNBUFFERED=1 TZ=UTC PO_PLAYWRIGHT=true

# Let Render inject the PORT
CMD ["sh", "-c", "python -m uvicorn po_svc:app --host 0.0.0.0 --port ${PORT:-8000}"]