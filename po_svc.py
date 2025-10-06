# po_svc.py
import os
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Header, Query

from scraper import fetch_candles

app = FastAPI()

def _bool(env: str, default: bool = False) -> bool:
    return os.getenv(env, "true" if default else "false").lower() == "true"

PO_SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "").strip()

async def auth(authorization: str = Header(None)):
    if not PO_SVC_TOKEN:
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1].strip()
    if token != PO_SVC_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/")
async def root():
    return {"ok": True}

@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "mock": _bool("PO_MOCK", False),
        "playwright": _bool("PLAYWRIGHT_READY", True),
        "headless": _bool("PO_HEADLESS", True),
        "base_url": os.getenv("PO_BASE_URL", "https://pocketoption.net/en/"),
    }

@app.get("/po/candles")
async def po_candles(
    symbol: str = Query(...),
    interval: str = Query(..., pattern="^(1m|5m|15m|30m|1h)$"),
    limit: int = Query(3, ge=1, le=200),
    _=Depends(auth),
) -> List[Dict[str, Any]]:
    try:
        return await fetch_candles(symbol, interval, limit)
    except HTTPException:
        raise
    except Exception as e:
        # Swallow Python stack and send concise error to client.
        raise HTTPException(status_code=500, detail=f"scraper error: {e}")