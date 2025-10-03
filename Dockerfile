FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# System deps (curl for health, tzdata optional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl tzdata && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render will expose PORT; default 8080
ENV PORT=8080
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
