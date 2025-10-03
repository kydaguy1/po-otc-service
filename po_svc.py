import os
import math
import time
import logging
from typing import List, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

try:
    # Will only be used when MOCK_PO=0
    from playwright.async_api import async_playwright  # type: ignore
    _PLAYWRIGHT_AVAILABLE = True
except Exception:
    _PLAYWRIGHT_AVAILABLE = False

# -------------------------
# Logging & App
# -------------------------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("po_svc")

app = FastAPI()

# -------------------------
# Env / Config
# -------------------------
PO_SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "")
PO_USER = os.getenv("PO_USER", "")
PO_PASS = os.getenv("PO_PASS", "")

# Default MOCK = 1 so you can verify end-to-end immediately.
# Set MOCK_PO=0 later to enable real Playwright scraping.
MOCK_PO = os.getenv("MOCK_PO", "1") in ("1", "true", "True", "YES", "yes")

# -------------------------
# Helpers
# -------------------------
def _check_auth(req: Request):
    auth = req.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer")
    token = auth.split(" ", 1)[1].strip()
    if not PO_SVC_TOKEN or token != PO_SVC_TOKEN:
        raise HTTPException(status_code=403, detail="Bad token")


def _interval_seconds(interval: str) -> int:
    m = interval.lower().strip()
    return {
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "60m": 3600,
    }.get(m, 60)


def _floor_ts(ts: int, step: int) -> int:
    return ts - (ts % step)


def _gen_mock_candles(symbol: str, interval: str, limit: int) -> List[Dict]:
    """
    Deterministic-ish synthetic candles so you can test the bot quickly.
    Uses a sine wave + tiny noise to create OHLC around a base price.
    """
    step = _interval_seconds(interval)
    now = int(time.time())
    start = _floor_ts(now, step) - step * (limit - 1)

    # Pick a base price per symbol so pairs look different
    base_map = {
        "EURUSD": 1.0720,
        "GBPUSD": 1.2600,
        "USDJPY": 150.00,
        "AUDUSD": 0.6600,
    }
    base = base_map.get(symbol.upper(), 1.0000)

    out: List[Dict] = []
    for i in range(limit):
        t = start + i * step
        # a slow wave so consecutive bars look plausible
        wave = 0.0005 * math.sin(i / 10.0)
        # tiny body
        body = 0.0001 * math.sin(i / 3.0)
        o = base + wave
        c = o + body
        high = max(o, c) + 0.00015
        low = min(o, c) - 0.00015
        out.append({"t": t, "o": round(o, 6), "h": round(high, 6), "l": round(low, 6), "c": round(c, 6)})
    return out


# -------------------------
# Routes
# -------------------------
@app.get("/healthz")
async def healthz():
    # HEAD probes may 405; GET returns 200 which is what we rely on.
    return {"ok": True, "mock": MOCK_PO, "playwright": _PLAYWRIGHT_AVAILABLE}


@app.get("/debug/env")
async def debug_env():
    # Do NOT return secrets; only presence/length
    return {
        "PO_USER_present": bool(PO_USER),
        "PO_USER_len": len(PO_USER),
        "PO_PASS_present": bool(PO_PASS),
        "PO_PASS_len": len(PO_PASS),
        "PO_SVC_TOKEN_present": bool(PO_SVC_TOKEN),
        "PO_SVC_TOKEN_len": len(PO_SVC_TOKEN),
        "MOCK_PO": MOCK_PO,
        "PLAYWRIGHT_AVAILABLE": _PLAYWRIGHT_AVAILABLE,
    }


@app.get("/po/candles")
async def po_candles(request: Request, symbol: str, interval: str = "1m", limit: int = 120):
    """
    Returns: list of candles [{"t": epoch, "o":float, "h":float, "l":float, "c":float}, ...]
    """
    _check_auth(request)

    # Basic validation
    if not symbol:
        raise HTTPException(400, "symbol required")
    if limit <= 0 or limit > 5000:
        raise HTTPException(400, "limit out of range")

    # MOCK path (default) — lets you verify the entire pipeline right now
    if MOCK_PO:
        data = _gen_mock_candles(symbol, interval, limit)
        return data[-limit:]

    # Real scraping path (enable by setting MOCK_PO=0)
    if not PO_USER or not PO_PASS:
        raise HTTPException(500, detail="PO_USER/PO_PASS not set")

    if not _PLAYWRIGHT_AVAILABLE:
        raise HTTPException(500, detail="Playwright not installed in this container")

    try:
        # TODO: Fill in real navigation + scraping steps here.
        # The following is a scaffold; you'll need to implement actual flow:
        #
        # 1) await page.goto("https://pocketoption.com/")
        # 2) login with PO_USER/PO_PASS (fill inputs, click, wait for nav)
        # 3) open the symbol chart (symbol param)
        # 4) switch timeframe (interval param)
        # 5) read visible candles; transform to [{"t","o","h","l","c"}]
        #
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context()
            page = await context.new_page()

            # --- BEGIN: placeholder flow ---
            # This is where you'd implement real login & scrape; for now raise to remind you.
            await browser.close()
            raise RuntimeError("Real scraping not implemented. Set MOCK_PO=1 to return synthetic candles.")
            # --- END: placeholder flow ---

    except HTTPException:
        raise
    except Exception as e:
        log.exception("Error in /po/candles")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
