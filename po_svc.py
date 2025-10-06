import os
from fastapi import FastAPI

app = FastAPI()

MOCK = os.getenv("PO_MOCK","true").lower()=="true"
PLAYWRIGHT_READY = os.getenv("PLAYWRIGHT_READY","false").lower()=="true"  # optional flag

@app.get("/")
async def root():
    return {"ok": True}

@app.get("/healthz")
async def healthz():
    return {"ok": True, "mock": MOCK, "playwright": PLAYWRIGHT_READY}
