FROM python:3.11-slim

# System deps Playwright needs
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates fonts-liberation libatk-bridge2.0-0 \
    libnss3 libxkbcommon0 libdrm2 libgbm1 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# >>> install Chromium for Playwright
RUN python -m playwright install --with-deps chromium

# Copy the app last (better layer caching)
COPY . .

ENV PORT=8000
CMD ["python", "-m", "uvicorn", "po_svc:app", "--host", "0.0.0.0", "--port", "8000"]
