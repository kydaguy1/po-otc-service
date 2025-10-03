# po_svc.py
import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# If you use Playwright or other libs, import them here
# from playwright.async_api import async_playwright

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("po_svc")

app = FastAPI()

PO_SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "")
PO_USER = os.getenv("PO_USER", "")
PO_PASS = os.getenv("PO_PASS", "")

def _check_auth(req: Request):
    auth = req.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer")
    token = auth.split(" ", 1)[1].strip()
    if not PO_SVC_TOKEN or token != PO_SVC_TOKEN:
        raise HTTPException(status_code=403, detail="Bad token")

@app.get("/healthz")
async def healthz():
    # HEAD requests were 405 before—this makes GET succeed; 405 is fine for HEAD.
    return {"ok": True}

@app.get("/po/candles")
async def po_candles(request: Request, symbol: str, interval: str = "1m", limit: int = 120):
    _check_auth(request)
    if not symbol:
        raise HTTPException(400, "symbol required")
    # If your scraper requires creds, enforce here so we fail with 400/500 clearly:
    if not PO_USER or not PO_PASS:
        raise HTTPException(500, "PO_USER/PO_PASS missing on server")

    try:
        # TODO: your Playwright scraping / candle build goes here.
        # Example skeleton:
        # async with async_playwright() as p:
        #     browser = await p.chromium.launch(headless=True)
        #     page = await browser.new_page()
        #     # login with PO_USER/PO_PASS, navigate, collect candles...
        #     await browser.close()
        #
        # For now, return a dummy structure to test 200s quickly:
        data = [
            {"t": 1727975400, "o": 1.0723, "h": 1.0725, "l": 1.0721, "c": 1.0724},
            {"t": 1727975460, "o": 1.0724, "h": 1.0727, "l": 1.0723, "c": 1.0726},
        ]
        return data[-limit:]

    except HTTPException:
        raise
    except Exception as e:
        log.exception("Error in /po/candles")
        # Surface the error text so you see it in curl/replit logs:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
