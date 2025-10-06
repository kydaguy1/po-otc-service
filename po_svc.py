# po_svc.py
import os
import time
from fastapi import FastAPI, Header, HTTPException, Query

app = FastAPI()

MOCK = os.getenv("PO_MOCK", "true").lower() == "true"
PLAYWRIGHT_READY = os.getenv("PLAYWRIGHT_READY", "false").lower() == "true"
SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "")

def _auth(authorization: str | None):
    if not SVC_TOKEN:  # open if no token configured
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.removeprefix("Bearer ").strip()
    if token != SVC_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/")
async def root():
    return {"ok": True}

@app.get("/healthz")
async def healthz():
    return {"ok": True, "mock": MOCK, "playwright": PLAYWRIGHT_READY}

@app.get("/po/candles")
async def candles(
    symbol: str = Query(..., description="e.g. EURUSD_OTC"),
    interval: str = Query("1m", description="1m/5m/etc"),
    limit: int = Query(120, ge=1, le=500),
    authorization: str | None = Header(None, alias="Authorization"),
):
    _auth(authorization)

    if MOCK:
        # Time-based mock so values actually change (useful for wiring tests)
        now = int(time.time() // 60 * 60)
        base = 1.07000 + (now % 13) / 10000.0
        out = []
        for i in range(limit):
            t = now - 60 * (limit - 1 - i)
            o = round(base + (i % 3) * 0.00003, 6)
            h = round(o + 0.00020, 6)
            l = round(o - 0.00020, 6)
            c = round(o + ((i % 2) * 2 - 1) * 0.00004, 6)
            out.append({"t": t, "o": o, "h": h, "l": l, "c": c})
        return out

    # REAL mode: call your Playwright scraper.
    # Implement fetch_candles(symbol, interval, limit) inside scraper.py.
    try:
        from scraper import fetch_candles  # you supply this
    except Exception as e:  # pragma: no cover
        raise HTTPException(
            status_code=501,
            detail=f"Real scraper not wired yet: {e}. Set PO_MOCK=true until scraper is implemented.",
        )
    data = await fetch_candles(symbol=symbol, interval=interval, limit=limit)
    return data
