# Simple, fast FastAPI image
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (curl only for debugging/health checks if needed)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY po_api.py po_svc.py scraper.py README.md /app/

# Expose default FastAPI port
EXPOSE 10000
# Render will run what you configure as the Start command; keeping a default:
CMD ["uvicorn", "po_api:app", "--host", "0.0.0.0", "--port", "10000"]