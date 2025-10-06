import os
import importlib
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.responses import JSONResponse

app = FastAPI()

# ---- env flags ----
MOCK = os.getenv("PO_MOCK", "true").lower() == "true"
PLAYWRIGHT_READY = os.getenv("PLAYWRIGHT_READY", "false").lower() == "true"

# optional bearer protection
PO_SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "").strip()

def require_bearer(authorization: Optional[str] = Header(None)) -> None:
    if not PO_SVC_TOKEN:
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(None, 1)[1]
    if token != PO_SVC_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/")
async def root():
    return {"ok": True}

@app.get("/healthz")
async def healthz():
    return {"ok": True, "mock": MOCK, "playwright": PLAYWRIGHT_READY}

def _load_scraper():
    """
    Import scraper.fetch_candles with a clear error if the module/function is missing.
    """
    try:
        mod = importlib.import_module("scraper")
    except Exception as e:
        raise HTTPException(
            status_code=501,
            detail=f"Importer error for scraper.py: {e}"
        )
    if not hasattr(mod, "fetch_candles"):
        raise HTTPException(
            status_code=501,
            detail="scraper.py present but missing function fetch_candles(symbol, interval, limit)"
        )
    return mod.fetch_candles

@app.get("/po/candles")
async def po_candles(
    symbol: str = Query(..., description="e.g., EURUSD_OTC"),
    interval: str = Query("1m"),
    limit: int = Query(120, ge=1, le=500),
    _: None = Depends(require_bearer),
):
    """
    Returns a list of candles: [{t,o,h,l,c}, ...]
    - If PO_MOCK=true, serves synthetic candles.
    - If PO_MOCK=false, calls scraper.fetch_candles(symbol, interval, limit).
    """
    if MOCK:
        # simple moving-price mock so you can see changes
        import time
        base = 1.071 + (int(time.time() // 60) % 7) * 0.0001
        candles = []
        now = int(time.time() // 60) * 60
        for i in range(limit):
            t = now - 60 * (limit - 1 - i)
            o = round(base + (i % 3) * 0.00005, 6)
            h = round(o + 0.00012, 6)
            l = round(o - 0.00012, 6)
            c = round(o + ((-1) ** i) * 0.00003, 6)
            candles.append({"t": t, "o": o, "h": h, "l": l, "c": c})
        return candles

    # real path
    fetch_candles = _load_scraper()
    try:
        data = await fetch_candles(symbol=symbol, interval=interval, limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        # surface scraper errors cleanly
        raise HTTPException(status_code=500, detail=f"scraper error: {e}")

    if not isinstance(data, list) or not data:
        raise HTTPException(status_code=502, detail="scraper returned no data")
    return data
