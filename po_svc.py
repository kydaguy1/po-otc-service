# po_svc.py
import os
from typing import List, Dict

from fastapi import FastAPI, HTTPException, Header, status, Query

from scraper import fetch_candles_async  # <-- async, we will await it

app = FastAPI()

PO_SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "").strip()
PO_MOCK = os.getenv("PO_MOCK", "false").lower() == "true"
PLAYWRIGHT_READY = os.getenv("PLAYWRIGHT_READY", "true").lower() == "true"
PO_HEADLESS = os.getenv("PO_HEADLESS", "true").lower() == "true"
PO_BASE_URL = os.getenv("PO_BASE_URL", "https://pocketoption.net/en/").strip()


@app.get("/")
async def root():
    return {"ok": True}


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "mock": PO_MOCK,
        "playwright": PLAYWRIGHT_READY,
        "headless": PO_HEADLESS,
        "base_url": PO_BASE_URL,
    }


def _check_auth(authorization: str | None):
    if not PO_SVC_TOKEN:
        return  # auth disabled
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != PO_SVC_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")


@app.get("/po/candles")
async def po_candles(
    symbol: str = Query(..., description="e.g. EURUSD_OTC"),
    interval: str = Query("1m", description="e.g. 1m"),
    limit: int = Query(3, ge=1, le=500),
    authorization: str | None = Header(None),
) -> List[Dict]:
    _check_auth(authorization)

    if PO_MOCK:
        # Simple moving mock so you can test wiring
        base = 1.0710
        out = []
        for i in range(limit):
            t = 1759770000 + 60 * i
            o = base + i * 0.0001
            h = o + 0.0002
            l = o - 0.0002
            c = o + 0.00005
            out.append({"t": t, "o": round(o, 5), "h": round(h, 5), "l": round(l, 5), "c": round(c, 5)})
        return out

    if not PLAYWRIGHT_READY:
        raise HTTPException(status_code=503, detail="Playwright not ready in this environment")

    try:
        # >>> IMPORTANT: we AWAIT the async scraper (no asyncio.run here)
        candles = await fetch_candles_async(symbol=symbol, interval=interval, limit=limit)
        return candles
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"scraper error: {e}")