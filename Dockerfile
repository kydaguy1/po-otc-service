FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render will pass $PORT. uvicorn will bind to it.
CMD ["python", "-m", "uvicorn", "po_svc:app", "--host", "0.0.0.0", "--port", "0"]