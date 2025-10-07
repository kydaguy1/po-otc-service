# po_api.py
import os
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from pydantic import BaseModel
from loguru import logger

import scraper  # our local scraper.py

app = FastAPI()

PO_SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "")
PO_BASE_URL  = os.getenv("PO_BASE_URL", "https://pocketoption.net/en/")
PO_HEADLESS  = os.getenv("PO_HEADLESS", "true").lower() == "true"
PLAYWRIGHT_READY = os.getenv("PLAYWRIGHT_READY", "true").lower() == "true"

def auth_check(authorization: str = Header(default="")) -> None:
    if not PO_SVC_TOKEN:
        raise HTTPException(status_code=401, detail="Service token not configured")
    try:
        scheme, token = authorization.split(" ", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    if scheme.lower() != "bearer" or token.strip() != PO_SVC_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    return {
        "ok": True,
        "mock": False,
        "playwright": True,
        "headless": PO_HEADLESS,
        "base_url": PO_BASE_URL,
    }

@app.get("/po/candles")
def get_candles(
    symbol: str = Query(..., description="e.g. EURUSD_OTC"),
    interval: str = Query("1m"),
    limit: int = Query(3, ge=1, le=500),
    _auth: None = Depends(auth_check),
) -> List[Dict[str, Any]]:
    # Call sync scraper; no asyncio.run here
    try:
        return scraper.fetch_candles(symbol=symbol, interval=interval, limit=limit)
    except Exception as e:
        logger.exception("scraper error")
        raise HTTPException(status_code=500, detail=f"scraper error: {e}")