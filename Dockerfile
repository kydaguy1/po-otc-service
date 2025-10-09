FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PYTHONUNBUFFERED=1

# Render will inject $PORT automatically
CMD exec uvicorn po_api:app --host 0.0.0.0 --port ${PORT:-8000}