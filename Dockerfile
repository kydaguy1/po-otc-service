# Use the Playwright image that matches the library version
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install matching browser binaries
RUN playwright install --with-deps chromium

# Copy the service code
COPY . .

# Render routes to $PORT (we'll listen on 8080 inside)
ENV PORT=8080
EXPOSE 8080

# ⬇️ If your FastAPI app is NOT in "po_svc.py", change module below accordingly
CMD ["uvicorn", "po_svc:app", "--host", "0.0.0.0", "--port", "8080"]
