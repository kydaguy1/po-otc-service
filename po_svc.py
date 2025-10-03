import os
import math
import time
import logging
from typing import List, Dict

from fastapi import FastAPI, HTTPException, Request

try:
    from playwright.async_api import async_playwright  # used when MOCK_PO=0
    _PLAYWRIGHT_AVAILABLE = True
except Exception:
    _PLAYWRIGHT_AVAILABLE = False

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("po_svc")

app = FastAPI()

PO_SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "")
PO_USER = os.getenv("PO_USER", "")
PO_PASS = os.getenv("PO_PASS", "")

MOCK_PO = os.getenv("MOCK_PO", "1") in ("1", "true", "True", "YES", "yes")

def _check_auth(req: Request):
    auth = req.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer")
    token = auth.split(" ", 1)[1].strip()
    if not PO_SVC_TOKEN or token != PO_SVC_TOKEN:
        raise HTTPException(status_code=403, detail="Bad token")

def _interval_seconds(interval: str) -> int:
    return {"1m":60,"3m":180,"5m":300,"15m":900,"30m":1800,"60m":3600}.get(interval.lower(), 60)

def _floor_ts(ts: int, step: int) -> int:
    return ts - (ts % step)

def _gen_mock_candles(symbol: str, interval: str, limit: int) -> List[Dict]:
    step = _interval_seconds(interval)
    now = int(time.time())
    start = _floor_ts(now, step) - step * (limit - 1)
    base_map = {"EURUSD":1.0720,"GBPUSD":1.2600,"USDJPY":150.0,"AUDUSD":0.6600}
    base = base_map.get(symbol.upper(), 1.0000)
    out: List[Dict] = []
    for i in range(limit):
        t = start + i*step
        wave = 0.0005 * math.sin(i/10.0)
        body = 0.0001 * math.sin(i/3.0)
        o = base + wave
        c = o + body
        h = max(o,c) + 0.00015
        l = min(o,c) - 0.00015
        out.append({"t": t, "o": round(o,6), "h": round(h,6), "l": round(l,6), "c": round(c,6)})
    return out

@app.get("/healthz")
async def healthz():
    return {"ok": True, "mock": MOCK_PO, "playwright": _PLAYWRIGHT_AVAILABLE}

@app.get("/debug/env")
async def debug_env():
    return {
        "PO_USER_present": bool(PO_USER), "PO_USER_len": len(PO_USER),
        "PO_PASS_present": bool(PO_PASS), "PO_PASS_len": len(PO_PASS),
        "PO_SVC_TOKEN_present": bool(PO_SVC_TOKEN), "PO_SVC_TOKEN_len": len(PO_SVC_TOKEN),
        "MOCK_PO": MOCK_PO, "PLAYWRIGHT_AVAILABLE": _PLAYWRIGHT_AVAILABLE,
    }

@app.get("/po/candles")
async def po_candles(request: Request, symbol: str, interval: str = "1m", limit: int = 120):
    _check_auth(request)
    if not symbol:
        raise HTTPException(400, "symbol required")
    if limit <= 0 or limit > 5000:
        raise HTTPException(400, "limit out of range")

    if MOCK_PO:
        return _gen_mock_candles(symbol, interval, limit)[-limit:]

    if not PO_USER or not PO_PASS:
        raise HTTPException(500, detail="PO_USER/PO_PASS not set")
    if not _PLAYWRIGHT_AVAILABLE:
        raise HTTPException(500, detail="Playwright not installed in container")

    try:
        # TODO: implement real login + scrape here when MOCK_PO=0
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context()
            page = await context.new_page()

            # --- implement actual flow here ---
            await browser.close()
            raise RuntimeError("Scraping not implemented. Set MOCK_PO=1 to return synthetic candles.")
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Error in /po/candles")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
