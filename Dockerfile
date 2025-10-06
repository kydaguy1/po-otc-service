FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Render injects PORT; bind to it
CMD python -m uvicorn po_svc:app --host 0.0.0.0 --port $PORT
