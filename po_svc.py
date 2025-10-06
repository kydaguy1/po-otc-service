# po_svc.py
import os
import logging
from typing import List
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from tenacity import retry, wait_fixed, stop_after_attempt
import asyncio

# our scraper
from scraper import fetch_candles  # async function

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
)
log = logging.getLogger("po-api")

app = FastAPI()

# --- Config from env
SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "")
MOCK = os.getenv("PO_MOCK", "false").lower() == "true"
PLAYWRIGHT_READY = os.getenv("PLAYWRIGHT_READY", "true").lower() == "true"
HEADLESS = os.getenv("PO_HEADLESS", "true").lower() == "true"
BASE_URL = os.getenv("PO_BASE_URL", "https://pocketoption.net/en/")
LOGIN_EMAIL = os.getenv("PO_LOGIN_EMAIL") or os.getenv("PO_USER", "")
LOGIN_PASSWORD = os.getenv("PO_LOGIN_PASSWORD") or os.getenv("PO_PASS", "")

class Candle(BaseModel):
    t: int
    o: float
    h: float
    l: float
    c: float

def auth_guard(authorization: str = Header(default="")):
    if not SVC_TOKEN:
        return
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if authorization.split(" ", 1)[1].strip() != SVC_TOKEN:
        raise HTTPException(status_code=401, detail="Bad token")

@app.get("/")
async def root():
    return {"ok": True}

@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "mock": MOCK,
        "playwright": PLAYWRIGHT_READY,
        "headless": HEADLESS,
        "base_url": BASE_URL,
    }

# Optional: warmup endpoint to pre-login (debug)
@app.post("/po/warmup")
async def warmup(_: None = Depends(auth_guard)):
    try:
        await fetch_candles(
            symbol="EURUSD_OTC", interval="1m", limit=1,
            headless=HEADLESS, base_url=BASE_URL,
            email=LOGIN_EMAIL, password=LOGIN_PASSWORD, warmup_only=True
        )
        return {"ok": True}
    except Exception as e:
        log.exception("warmup failed")
        raise HTTPException(500, detail=f"warmup error: {e}")

@retry(wait=wait_fixed(2), stop=stop_after_attempt(2))
async def _do_fetch(symbol: str, interval: str, limit: int) -> List[Candle]:
    return await fetch_candles(
        symbol=symbol, interval=interval, limit=limit,
        headless=HEADLESS, base_url=BASE_URL,
        email=LOGIN_EMAIL, password=LOGIN_PASSWORD
    )

@app.get("/po/candles", response_model=List[Candle])
async def po_candles(symbol: str, interval: str = "1m", limit: int = 3, _: None = Depends(auth_guard)):
    if MOCK:
        # simple moving mock (changes a bit each call)
        import time, random
        now = int(time.time()) // 60 * 60
        out = []
        last = 1.07100 + random.random() * 0.0006
        for i in range(limit, 0, -1):
            t = now - i * 60
            o = round(last, 5)
            h = round(o + 0.0002, 5)
            l = round(o - 0.0002, 5)
            c = round(o + random.uniform(-0.00015, 0.00015), 5)
            out.append({"t": t, "o": o, "h": h, "l": l, "c": c})
            last = c
        return out

    if not PLAYWRIGHT_READY:
        raise HTTPException(503, detail="Playwright not ready on this service")

    if not LOGIN_EMAIL or not LOGIN_PASSWORD:
        raise HTTPException(400, detail="PO_LOGIN_EMAIL/PO_LOGIN_PASSWORD not set")

    try:
        candles = await _do_fetch(symbol, interval, limit)
        return candles
    except Exception as e:
        log.exception("po_candles error")
        raise HTTPException(500, detail=f"scraper error: {e}")