# Playwright + Python base (Chromium preinstalled)
# If you ever see a "Executable doesn't exist at /ms-playwright/..." mismatch,
# switch the tag to the version Playwright requests in the error.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

# install deps first (better cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy app
COPY . .

ENV PYTHONUNBUFFERED=1 TZ=UTC PO_PLAYWRIGHT=true

# IMPORTANT: use shell so ${PORT} resolves (Render provides PORT)
CMD ["sh", "-c", "python -m uvicorn po_svc:app --host 0.0.0.0 --port ${PORT:-8000}"]