# Match Playwright libs to the Python package version above
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=10000

WORKDIR /app

# Install deps first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ensure browsers/deps are present (the base image has them,
# but this keeps future changes safe)
RUN python -m playwright install --with-deps chromium

# Copy app
COPY . .

# Expose Render port
EXPOSE 10000

# Start the API
CMD ["uvicorn", "po_api:app", "--host", "0.0.0.0", "--port", "10000"]