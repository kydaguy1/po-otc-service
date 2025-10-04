# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps (lightweight)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential \
 && rm -rf /var/lib/apt/lists/*

# Copy reqs first for better caching
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest
COPY . .

# Make sure Python can import from /app no matter where Render launches from
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8000

# IMPORTANT: your code must have `main.py` at repo root and inside it: `app = FastAPI()`
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "0.0.0.0:$PORT"]
