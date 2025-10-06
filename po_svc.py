# po_svc.py
import os
import asyncio
from typing import List, Literal
from fastapi import FastAPI, Depends, HTTPException, Query, Header
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_fixed

# --- Auth --------------------------------------------------------------------
PO_SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "").strip()

def require_bearer(authorization: str = Header(None)):
    if not PO_SVC_TOKEN:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1].strip()
    if token != PO_SVC_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

# --- App ---------------------------------------------------------------------
app = FastAPI()

MOCK = os.getenv("PO_MOCK", "false").lower() == "true"
HEADLESS = os.getenv("PO_HEADLESS", "true").lower() == "true"
PO_USER = os.getenv("PO_USER", "")
PO_PASS = os.getenv("PO_PASS", "")

# Playwright bits (filled on startup if MOCK is False)
_playwright = None
_browser = None
_context = None
_page = None
_playwright_ready = False

@app.on_event("startup")
async def startup():
    global _playwright, _browser, _context, _page, _playwright_ready
    if MOCK:
        return
    from playwright.async_api import async_playwright
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(headless=HEADLESS)
    _context = await _browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent="Mozilla/5.0 (RenderPlaywrightBot)"
    )
    _page = await _context.new_page()

    # --- login once (adapt selectors to your existing login flow) -------------
    await _page.goto("https://pocketoption.com/en/")
    # TODO: replace with your actual login steps/selectors
    # await _page.click("text=Log in")
    # await _page.fill("input[type='email']", PO_USER)
    # await _page.fill("input[type='password']", PO_PASS)
    # await _page.click("button:has-text('Sign in')")
    # await _page.wait_for_load_state("networkidle")

    _playwright_ready = True

@app.on_event("shutdown")
async def shutdown():
    global _playwright, _browser, _context, _page
    try:
        if _context: await _context.close()
        if _browser: await _browser.close()
        if _playwright: await _playwright.stop()
    finally:
        _playwright = _browser = _context = _page = None

# --- Models ------------------------------------------------------------------
class Candle(BaseModel):
    t: int
    o: float
    h: float
    l: float
    c: float

# --- Mock helper --------------------------------------------------------------
def mock_candles(n=120) -> List[Candle]:
    import time, random
    base = time.time() // 60 * 60
    out = []
    last = 1.071
    for i in range(n):
        ts = int(base - 60*(n-i))
        o = last
        c = round(o + random.uniform(-0.0003, 0.0003), 6)
        h = max(o, c) + 0.0001
        l = min(o, c) - 0.0001
        last = c
        out.append(Candle(t=ts, o=o, h=h, l=l, c=c))
    return out

# --- Real scraping (stub; call your existing routine) ------------------------
@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
async def get_candles_real(symbol: str, interval: Literal["1m","5m","15m"], limit: int) -> List[Candle]:
    """
    Replace the body with your existing Playwright scraping routine that
    reads OTC candles from the chart. This stub shows structure & returns
    at least the last 'limit' candles.
    """
    if not _playwright_ready:
        raise RuntimeError("Playwright not ready")

    # Example structure: navigate / ensure symbol + TF, read last candles JSON
    # await ensure_symbol_and_timeframe(_page, symbol, interval)
    # candles = await read_candles_from_chart(_page, limit)
    # return [Candle(**c) for c in candles]

    # TEMP: until your selectors are wired, raise an error so you notice
    raise RuntimeError("Wire up Playwright selectors to return real candles")

# --- Routes ------------------------------------------------------------------
@app.get("/")
async def root():
    return {"ok": True}

@app.get("/healthz")
async def healthz():
    return {"ok": True, "mock": MOCK, "playwright": (not MOCK and _playwright_ready)}

@app.get("/po/candles", response_model=List[Candle], dependencies=[Depends(require_bearer)])
async def po_candles(
    symbol: str = Query(..., description="e.g. EURUSD_OTC"),
    interval: Literal["1m","5m","15m"] = "1m",
    limit: int = Query(120, ge=1, le=500)
):
    if MOCK:
        data = mock_candles(limit)
        return data[-limit:]
    # real mode
    return await get_candles_real(symbol, interval, limit)
