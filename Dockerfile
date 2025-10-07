# Dockerfile
# Use a Playwright image that matches the browsers bundled (1.45.0 works well on Render)
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

# Prevents Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Install Python deps (uvicorn, fastapi already minimal; playwright libs provided by base)
RUN pip install --no-cache-dir fastapi uvicorn[standard] tenacity

# Copy app
WORKDIR /app
COPY po_svc.py /app/po_svc.py
COPY scraper.py /app/scraper.py

# Render provides $PORT
ENV PORT=10000

# Expose for clarity (Render still injects PORT)
EXPOSE 10000

# Start the API (NO dev reload, NO blocking preloads)
CMD ["sh", "-c", "python -m uvicorn po_svc:app --host 0.0.0.0 --port ${PORT}"]