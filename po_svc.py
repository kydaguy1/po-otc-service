# po_svc.py (Render service)
import os, time
from fastapi import FastAPI, Query, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

app = FastAPI()
security = HTTPBearer()

PO_SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "")

def require_token(creds: HTTPAuthorizationCredentials = Depends(security)):
    if not PO_SVC_TOKEN:
        return  # token check disabled if not set
    if creds.credentials != PO_SVC_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

MOCK = os.getenv("PO_MOCK", "false").lower() == "true"
PLAYWRIGHT_READY = os.getenv("PLAYWRIGHT_READY", "false").lower() == "true"

@app.get("/")
async def root():
    return {"ok": True}

@app.get("/healthz")
async def healthz():
    return {"ok": True, "mock": MOCK, "playwright": PLAYWRIGHT_READY}

@app.get("/po/candles")
async def po_candles(
    symbol: str = Query(..., description="e.g. EURUSD_OTC"),
    interval: str = Query(..., description="e.g. 1m"),
    limit: int = Query(3, ge=1, le=1000),
    _auth: None = Depends(require_token),
):
    """
    GET with query params, not body.
    """
    # If you have a real scraper wired, call it here.
    # from scraper import fetch_candles
    # return await fetch_candles(symbol=symbol, interval=interval, limit=limit)

    # Temporary sample data so the endpoint works immediately:
    now = int(time.time() // 60 * 60)
    base = 1.071
    out = []
    for i in range(limit, 0, -1):
        b = base + (i % 7) * 0.0001
        out.append({"t": now - i*60, "o": b, "h": b+0.00015, "l": b-0.00015, "c": b+0.00005})
    return out