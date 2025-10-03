FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "uvicorn", "po_svc:app", "--host", "0.0.0.0", "--port", "8080"]
