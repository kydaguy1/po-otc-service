# Dockerfile
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONUNBUFFERED=1 TZ=UTC

# Render sets $PORT; use sh -c so ${PORT} expands
CMD ["sh", "-c", "python -m uvicorn po_svc:app --host 0.0.0.0 --port ${PORT:-8000}"]