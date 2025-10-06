# po_svc.py
import os
import time
from fastapi import FastAPI, Header, HTTPException, Query

app = FastAPI()

MOCK = os.getenv("PO_MOCK", "true").lower() == "true"
PLAYWRIGHT_READY = os.getenv("PLAYWRIGHT_READY", "false").lower() == "true"
SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "")

def _auth(authorization: str | None):
    if not SVC_TOKEN:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if authorization.removeprefix("Bearer ").strip() != SVC_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.on_event("startup")
async def _on_startup():
    if not MOCK:
        try:
            from scraper import startup
            await startup()
        except Exception as e:
            # We still start; health will report playwright:false if desired
            print("SCRAPER startup error:", e)

@app.on_event("shutdown")
async def _on_shutdown():
    if not MOCK:
        try:
            from scraper import shutdown
            await shutdown()
        except Exception as e:
            print("SCRAPER shutdown error:", e)

@app.get("/")
async def root():
    return {"ok": True}

@app.get("/healthz")
async def healthz():
    return {"ok": True, "mock": MOCK, "playwright": PLAYWRIGHT_READY}

@app.get("/po/candles")
async def candles(
    symbol: str = Query(..., description="e.g. EURUSD_OTC"),
    interval: str = Query("1m"),
    limit: int = Query(120, ge=1, le=500),
    authorization: str | None = Header(None, alias="Authorization"),
):
    _auth(authorization)

    if MOCK:
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

    from scraper import fetch_candles
    try:
        return await fetch_candles(symbol=symbol, interval=interval, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scraper failed: {e}")
