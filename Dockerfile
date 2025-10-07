FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

ENV PYTHONUNBUFFERED=1

# Install FastAPI and uvicorn
RUN pip install --no-cache-dir fastapi uvicorn[standard] tenacity

# Copy app
WORKDIR /app
COPY po_svc.py /app/po_svc.py
COPY scraper.py /app/scraper.py

ENV PORT=10000
EXPOSE 10000

CMD ["sh", "-c", "python -m uvicorn po_svc:app --host 0.0.0.0 --port ${PORT}"]