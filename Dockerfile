# Playwright + Python (Chromium preinstalled) — pin to v1.45.0 as requested by Playwright
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app
COPY . .

# (DNS) Some hosts resolve fine, others don't. If resolv.conf is writable (not a symlink),
# write public resolvers so Page.goto won't fail with net::ERR_NAME_NOT_RESOLVED
RUN if [ ! -L /etc/resolv.conf ]; then \
      printf "nameserver 1.1.1.1\nnameserver 8.8.8.8\n" > /etc/resolv.conf ; \
    fi

ENV PYTHONUNBUFFERED=1 TZ=UTC

# IMPORTANT: Render provides $PORT — use shell so it expands
CMD ["sh","-c","python -m uvicorn po_svc:app --host 0.0.0.0 --port ${PORT:-8000}"]