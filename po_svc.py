# po_svc.py
import os
import time
import json
import logging
from datetime import datetime, timezone
from importlib import import_module
from typing import Optional, List

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse

log = logging.getLogger("po-api")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(title="PocketOption OTC microservice")

# ---- env helpers (NO heavy work at import time) -----------------------------
PO_SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "").strip()
PO_MOCK = os.getenv("PO_MOCK", "true").lower() == "true"
PO_BASE_URL = os.getenv("PO_BASE_URL", "https://pocketoption.net/en/").strip()
PO_HEADLESS = os.getenv("PO_HEADLESS", "true").lower() == "true"
PO_LOGIN_EMAIL = os.getenv("PO_LOGIN_EMAIL", "").strip()
PO_LOGIN_PASSWORD = os.getenv("PO_LOGIN_PASSWORD", "").strip()
PLAYWRIGHT_READY = os.getenv("PLAYWRIGHT_READY", "true").lower() == "true"


def _require_auth(authorization: Optional[str]) -> None:
    if not PO_SVC_TOKEN:
        raise HTTPException(status_code=500, detail="Service token not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    if token != PO_SVC_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


def _mock_candles(limit: int) -> List[dict]:
    """
    Generate plausible, CHANGING candles. Stable and fast.
    """
    now = int(time.time() // 60 * 60)  # round to minute
    base = 1.071 + (time.time() % 7) * 1e-3  # wiggle so it changes
    out = []
    for i in range(limit):
        ts = now - (limit - 1 - i) * 60
        o = round(base + (i % 3) * 1e-4, 6)
        h = round(o + 0.00016, 6)
        l = round(o - 0.00018, 6)
        c = round((o + l + h) / 3, 6)
        out.append({"t": ts, "o": o, "h": h, "l": l, "c": c})
    return out


@app.get("/")
def root():
    return {"ok": True}


@app.get("/healthz")
def healthz():
    # IMPORTANT: strictly no scraping / heavy imports here
    return {
        "ok": True,
        "mock": PO_MOCK,
        "playwright": PLAYWRIGHT_READY,
        "headless": PO_HEADLESS,
        "base_url": PO_BASE_URL,
    }


@app.get("/po/candles")
async def po_candles(
    symbol: str = Query(..., min_length=3),
    interval: str = Query("1m"),
    limit: int = Query(3, ge=1, le=500),
    authorization: Optional[str] = Header(None),
):
    """
    Returns an array of {t,o,h,l,c}. Uses mock when PO_MOCK=true.
    Requires Bearer <PO_SVC_TOKEN>.
    """
    _require_auth(authorization)

    if PO_MOCK:
        candles = _mock_candles(limit)
        return JSONResponse(candles)

    # real scraper path
    if not PLAYWRIGHT_READY:
        raise HTTPException(status_code=503, detail="Playwright not ready")

    if not PO_LOGIN_EMAIL or not PO_LOGIN_PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="scraper error: PO_LOGIN_EMAIL / PO_LOGIN_PASSWORD not set",
        )

    try:
        # Import lazily so healthz is always instant
        scraper = import_module("scraper")
    except ModuleNotFoundError as e:
        raise HTTPException(
            status_code=501,
            detail=f"Real scraper not wired yet: {e}. Set PO_MOCK=true until scraper is implemented.",
        )

    try:
        log.info(
            "INFO:scraper:fetch_candles: %s %s limit=%s headless=%s",
            symbol, interval, limit, PO_HEADLESS,
        )
        data = await scraper.fetch_candles(
            symbol=symbol,
            interval=interval,
            limit=limit,
            base_url=PO_BASE_URL,
            headless=PO_HEADLESS,
            email=PO_LOGIN_EMAIL,
            password=PO_LOGIN_PASSWORD,
            logger=log,
        )
        # Expect list[dict] with t,o,h,l,c
        return JSONResponse(data)
    except Exception as e:
        # Never crash the server; return a clear error
        msg = f"scraper error: {e}"
        log.exception(msg)
        raise HTTPException(status_code=500, detail=msg)


if __name__ == "__main__":
    # Local run: uvicorn po_svc:app --reload
    import uvicorn

    uvicorn.run(
        "po_svc:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )