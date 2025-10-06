# Dockerfile
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

# Only what we actually need to run the API
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code last (better layer caching)
COPY . .

# Helpful defaults
ENV PYTHONUNBUFFERED=1 \
    TZ=UTC

# Uvicorn must bind to $PORT on Render
CMD ["python","-m","uvicorn","po_svc:app","--host","0.0.0.0","--port","${PORT}"]
