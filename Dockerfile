FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY po_svc.py .
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "po_svc:app", "--host", "0.0.0.0", "--port", "8080"]
