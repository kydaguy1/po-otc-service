# po_svc.py
import os
import json
import logging
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# ---- configuration via env
MOCK = os.getenv("PO_MOCK", "false").lower() == "true"
PLAYWRIGHT_READY = os.getenv("PLAYWRIGHT_READY", "false").lower() == "true"
SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "")  # optional bearer
TZ = os.getenv("TZ", "UTC")

# logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("po-api")

# optional auth
bearer = HTTPBearer(auto_error=False)

def require_auth(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if not SVC_TOKEN:
        return True  # auth disabled
    if not creds or creds.scheme.lower() != "bearer" or creds.credentials != SVC_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

app = FastAPI(title="PO OTC service")

@app.get("/")
async def root():
    return {"ok": True}

@app.get("/healthz")
async def healthz():
    return {"ok": True, "mock": MOCK, "playwright": PLAYWRIGHT_READY}

# ---- mock data
def _mock_candles(limit: int) -> List[Dict[str, Any]]:
    import time, random
    now = int(time.time() // 60 * 60)
    out = []
    price = 1.07150
    for i in range(limit)[::-1]:
        t = now - i * 60
        o = price + random.uniform(-0.0002, 0.0002)
        h = o + random.uniform(0.0, 0.0003)
        l = o - random.uniform(0.0, 0.0003)
        c = o + random.uniform(-0.0002, 0.0002)
        out.append({"t": t, "o": round(o, 6), "h": round(h, 6), "l": round(l, 6), "c": round(c, 6)})
        price = c
    return out

# ---- real endpoint
@app.get("/po/candles", response_class=JSONResponse)
async def po_candles(
    symbol: str = Query(..., description="e.g. EURUSD_OTC"),
    interval: str = Query("1m", description="1m only for now"),
    limit: int = Query(120, ge=1, le=200),
    _auth_ok: bool = Depends(require_auth),
):
    if MOCK:
        return _mock_candles(limit)

    if not PLAYWRIGHT_READY:
        # clearly tell the caller what to fix
        raise HTTPException(status_code=503, detail="Playwright is not ready on this instance. Set PLAYWRIGHT_READY=true and redeploy.")

    try:
        from scraper import fetch_candles  # <- provided below
    except Exception as e:
        log.exception("Importer error for scraper.py")
        raise HTTPException(
            status_code=501,
            detail=f"Real scraper not wired yet: {e}. Set PO_MOCK=true until scraper is implemented."
        )

    try:
        candles = await fetch_candles(symbol=symbol, interval=interval, limit=limit)
        if not candles:
            raise HTTPException(status_code=502, detail="Scraper returned no data.")
        # Normalize + truncate to 'limit'
        out = [
            {"t": int(c["t"]), "o": float(c["o"]), "h": float(c["h"]), "l": float(c["l"]), "c": float(c["c"])}
            for c in candles
        ]
        return out[-limit:]
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Scraper failed")
        raise HTTPException(status_code=500, detail=f"Scraper failed: {e}")
