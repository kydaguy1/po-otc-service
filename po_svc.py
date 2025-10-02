import os, asyncio, json
from typing import List, Dict
from fastapi import FastAPI, HTTPException, Header, Query
from playwright.async_api import async_playwright

PO_USER = os.environ.get("PO_USER")
PO_PASS = os.environ.get("PO_PASS")
SVC_TOKEN = os.environ.get("PO_SVC_TOKEN")

if not SVC_TOKEN:
    raise RuntimeError("PO_SVC_TOKEN env var is required")

app = FastAPI(title="Pocket Option OTC Candles Service")

_browser = None
_pw = None

async def ensure_browser():
    global _browser, _pw
    if _browser and _browser.is_connected():
        return _browser
    _pw = await async_playwright().start()
    _browser = await _pw.chromium.launch(headless=True, args=["--no-sandbox"])
    return _browser

async def fetch_candles(symbol: str, interval: str, limit: int) -> List[Dict]:
    """Login to Pocket Option and capture candle data from network responses.
    NOTE: UI/endpoint changes may require selector tweaks.
    """
    browser = await ensure_browser()
    ctx = await browser.new_context()
    page = await ctx.new_page()

    if not (PO_USER and PO_PASS):
        await ctx.close()
        raise RuntimeError("PO_USER/PO_PASS not set")

    await page.goto("https://pocketoption.com/en/")
    await page.wait_for_load_state("domcontentloaded")

    try:
        await page.click('text=Sign in', timeout=8000)
    except Exception:
        pass

    await page.wait_for_selector('input[name="email"]', timeout=25000)
    await page.fill('input[name="email"]', PO_USER)
    await page.fill('input[type="password"]', PO_PASS)

    for label in ["Sign in", "Log in", "Login"]:
        try:
            await page.click(f'button:has-text("{label}")', timeout=4000)
            break
        except Exception:
            continue

    await page.wait_for_load_state("networkidle")

    # Navigate to assets page (adjust if needed)
    await page.goto("https://pocketoption.com/en/cabinet/assets/")
    await page.wait_for_load_state("networkidle")

    results: List[Dict] = []

    def try_parse(body: str) -> List[Dict]:
        import json, math
        try:
            j = json.loads(body)
        except Exception:
            return []
        out = []
        seq = j.get("data") or j.get("candles") or j.get("result") or []
        for r in seq:
            try:
                t = int(r.get("time") or r.get("t") or r.get("timestamp"))
                o = float(r.get("open") or r.get("o"))
                h = float(r.get("high") or r.get("h", o))
                l = float(r.get("low")  or r.get("l", o))
                c = float(r.get("close") or r.get("c", o))
                out.append({"t": t, "o": o, "h": h, "l": l, "c": c})
            except Exception:
                continue
        return out

    async def capture(resp):
        try:
            url = resp.url.lower()
            if any(k in url for k in ["candle", "candles", "time_series", "kline", "bars"]):
                body = await resp.text()
                data = try_parse(body)
                if data:
                    results.clear()
                    results.extend(data)
        except Exception:
            pass

    page.on("response", lambda r: asyncio.create_task(capture(r)))

    # Give it time to capture a response
    await asyncio.sleep(4.0)
    await ctx.close()
    return results[-limit:] if results else []

@app.get("/healthz")
async def healthz():
    return {"ok": True}

@app.get("/po/candles")
async def po_candles(
    symbol: str = Query(..., description="e.g., EURUSD"),
    interval: str = Query("1m", description="1m, 5m, etc"),
    limit: int = Query(200, ge=1, le=2000),
    authorization: str | None = Header(None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "No token")
    if authorization.split(" ", 1)[1] != SVC_TOKEN:
        raise HTTPException(403, "Bad token")
    try:
        data = await fetch_candles(symbol.upper(), interval, limit)
        if not data:
            raise HTTPException(502, "No data captured (UI changed or blocked).")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"error: {e}")
