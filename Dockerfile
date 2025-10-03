# Use the Playwright image that matches the required browser version
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ensure matching browser binaries are installed
RUN playwright install --with-deps chromium

# Copy app code
COPY . .

# Render will route traffic to this port
ENV PORT=8080
EXPOSE 8080

# ⚠️ If your file is NOT "po_svc.py", change "po_svc:app" accordingly:
# e.g., if it's main.py with FastAPI "app", use ["uvicorn", "main:app", ...]
CMD ["uvicorn", "po_svc:app", "--host", "0.0.0.0", "--port", "8080"]
