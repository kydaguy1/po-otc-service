# po_api.py
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import JSONResponse
import os
from typing import Optional

app = FastAPI()

PO_REQUIRE_AUTH = os.getenv("PO_REQUIRE_AUTH", "true").lower() == "true"
PO_SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "")
PO_MOCK = os.getenv("PO_MOCK", "false").lower() == "true"
PO_PLAYWRIGHT = os.getenv("PO_PLAYWRIGHT", "true").lower() == "true"

@app.get("/")
async def root():
    # Render probes HEAD/GET / during cold start. Keep this trivial.
    return {"ok": True}

@app.get("/healthz")
async def healthz():
    # Absolutely no heavy imports or network here.
    return {
        "ok": True,
        "mock": PO_MOCK,
        "playwright": PO_PLAYWRIGHT,
        "auth_required": PO_REQUIRE_AUTH,
    }

def _check_auth(authorization: Optional[str]) -> None:
    if not PO_REQUIRE_AUTH:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not PO_SVC_TOKEN or token != PO_SVC_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/po/candles")
async def po_candles(
    symbol: str = Query(..., alias="symbol"),
    interval: str = Query("1m", alias="interval"),
    limit: int = Query(120, ge=1, le=500),
    authorization: Optional[str] = Header(default=None, convert_underscores=False),
):
    _check_auth(authorization)

    # Mock mode
    if PO_MOCK:
        import time
        base = 1.07100
        now = int(time.time() // 60 * 60)
        rows = []
        for i in range(limit):
            t = now - (limit - 1 - i) * 60
            o = base + i * 0.00007
            h = o + 0.00015
            l = o - 0.00015
            c = o + 0.00005
            rows.append({"t": t, "o": round(o, 6), "h": round(h, 6), "l": round(l, 6), "c": round(c, 6)})
        return JSONResponse(rows)

    # Real scraper path
    if not PO_PLAYWRIGHT:
        raise HTTPException(status_code=503, detail="Playwright not enabled on server")

    try:
        # Lazy import so /healthz never pays the cost
        from scraper import fetch_candles  # you’ll add this file below
    except Exception as e:
        # Clear message when scraper is missing/misconfigured
        raise HTTPException(
            status_code=501,
            detail=f"Real scraper not wired yet: {e}. Set PO_MOCK=true until scraper is implemented."
        )

    try:
        rows = await fetch_candles(symbol=symbol, interval=interval, limit=limit)
        if not isinstance(rows, list):
            raise ValueError("scraper returned non-list")
        return JSONResponse(rows)
    except HTTPException:
        raise
    except Exception as e:
        # Never hang: always fail fast with an explanation
        raise HTTPException(status_code=500, detail=f"scraper error: {e}")
