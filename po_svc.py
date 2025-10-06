import os
import logging
from typing import List, Dict, Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse

# ---- logging ----
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("po-svc")

# ---- env ----
PO_MOCK = os.getenv("PO_MOCK", "false").lower() == "true"
PLAYWRIGHT_READY = os.getenv("PLAYWRIGHT_READY", "true").lower() == "true"
PO_HEADLESS = os.getenv("PO_HEADLESS", "true").lower() == "true"
PO_BASE_URL = os.getenv("PO_BASE_URL", "https://pocketoption.net/en/")

# service token to protect /po endpoints
PO_SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "")

# Try to import the scraper only if not mocking
fetch_candles_async = None
if not PO_MOCK:
    try:
        from scraper import fetch_candles_async  # async function
    except Exception as e:
        log.exception("Importer error for scraper.py")
        # Leave fetch_candles_async as None; we’ll error at request time.

app = FastAPI()


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


def _require_bearer(authz: str | None):
    if not PO_SVC_TOKEN:
        # If you didn’t set a token, allow everything (dev mode).
        return
    if not authz or not authz.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authz.split(" ", 1)[1].strip()
    if token != PO_SVC_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/po/candles")
async def po_candles(
    symbol: str = Query(..., example="EURUSD_OTC"),
    interval: str = Query(..., example="1m"),
    limit: int = Query(3, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    """
    Returns recent candles as:
    [{"t": <epoch>, "o": <float>, "h": <float>, "l": <float>, "c": <float>}]
    """
    _require_bearer(authorization)

    log.info("po_candles called: symbol=%s interval=%s limit=%s mock=%s",
             symbol, interval, limit, PO_MOCK)

    # Mock branch
    if PO_MOCK:
        import time
        now = int(time.time() // 60 * 60)
        series = []
        for i in range(limit, 0, -1):
            t = now - i * 60
            # Tiny, changing values for sanity checks
            base = 1.071 + (i * 0.00001)
            series.append({
                "t": t,
                "o": round(base, 5),
                "h": round(base + 0.00015, 5),
                "l": round(base - 0.00015, 5),
                "c": round(base + 0.00005, 5),
            })
        log.info("mock returned %d candles", len(series))
        return series

    # Real branch
    if not PLAYWRIGHT_READY:
        raise HTTPException(status_code=503, detail="Playwright not ready")

    if fetch_candles_async is None:
        # import failed during startup
        raise HTTPException(
            status_code=501,
            detail="Real scraper not wired yet: import of 'scraper' failed (see logs). "
                   "Set PO_MOCK=true until scraper is implemented.",
        )

    try:
        # Hard cap to keep requests from hanging forever
        import asyncio
        log.info("starting scraper fetch…")
        candles: List[Dict[str, Any]] = await asyncio.wait_for(
            fetch_candles_async(symbol=symbol, interval=interval, limit=limit),
            timeout=70,   # total request cap
        )
        log.info("scraper returned %d candles", len(candles))
        return JSONResponse(candles)
    except asyncio.TimeoutError:
        log.error("scraper timed out")
        raise HTTPException(status_code=504, detail="scraper timeout")
    except HTTPException:
        raise
    except Exception as e:
        log.exception("scraper error")
        raise HTTPException(status_code=500, detail=f"scraper error: {e}")