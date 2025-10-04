# Dockerfile
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render provides PORT; keep a default for local runs
ENV PORT=8000
EXPOSE 8000

# 👈 IMPORTANT: entrypoint is po_svc:app (not main:app)
CMD ["sh","-c","python -m uvicorn po_svc:app --host 0.0.0.0 --port ${PORT}"]
