# scraper.py
import os
import json
import asyncio
import logging
from typing import List, Dict, Any
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Page

log = logging.getLogger("scraper")
logging.basicConfig(level=logging.INFO)

# ---- env-configurable paths/selectors so you can tweak without code changes
PO_USER = os.getenv("PO_USER", "")
PO_PASS = os.getenv("PO_PASS", "")
PO_HEADLESS = os.getenv("PO_HEADLESS", "true").lower() == "true"

# If Pocket Option changes URLs, adjust these in Render env and redeploy
PO_LOGIN_URL   = os.getenv("PO_LOGIN_URL",   "https://pocketoption.com/en/cabinet/")
PO_TRADE_URL   = os.getenv("PO_TRADE_URL",   "https://pocketoption.com/en/cabinet/trade/")
# Pattern the site uses to return candle data (substring check)
PO_CANDLES_PAT = os.getenv("PO_CANDLES_PAT", "/candles")

NAV_TIMEOUT_MS = int(os.getenv("PO_NAV_TIMEOUT_MS", "45000"))
RESP_TIMEOUT_MS = int(os.getenv("PO_RESP_TIMEOUT_MS", "45000"))

@asynccontextmanager
async def browser_context():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=PO_HEADLESS, args=["--no-sandbox"])
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            java_script_enabled=True,
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari"
        )
        try:
            yield context
        finally:
            await context.close()
            await browser.close()

async def _login_and_open_trade(page: Page):
    # 1) open login
    log.info("NAV login: %s", PO_LOGIN_URL)
    await page.goto(PO_LOGIN_URL, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")

    # 2) If already logged in, skip (trade link visible)
    if "/cabinet/trade" in page.url:
        return

    # Common selectors — adjust via env if needed
    sel_email = os.getenv("PO_EMAIL_SEL", 'input[type="email"], input[name="email"]')
    sel_pass  = os.getenv("PO_PASS_SEL",  'input[type="password"], input[name="password"]')
    sel_btn   = os.getenv("PO_SUBMIT_SEL",'button[type="submit"], button:has-text("Sign in"), button:has-text("Log in")')

    # Some pages render a sign-in gating modal; wait for at least email OR trade link
    await page.wait_for_timeout(500)  # small settle
    if not await page.query_selector(sel_email):
        # page may redirect directly to trade if already logged in
        log.info("Email field not found; trying to go to trade URL")
        await page.goto(PO_TRADE_URL, timeout=NAV_TIMEOUT_MS)
    else:
        # 3) fill & submit
        await page.fill(sel_email, PO_USER)
        await page.fill(sel_pass, PO_PASS)
        await page.click(sel_btn)
        # wait for redirect or trade page to load
        await page.wait_for_timeout(800)
        try:
            await page.wait_for_url(lambda u: "/cabinet/trade" in u, timeout=NAV_TIMEOUT_MS)
        except Exception:
            # fallback: manually go
            await page.goto(PO_TRADE_URL, timeout=NAV_TIMEOUT_MS)

    # wait for chart UI (very loose heuristic)
    await page.wait_for_timeout(1000)

async def fetch_candles(symbol: str, interval: str, limit: int) -> List[Dict[str, Any]]:
    """
    Opens the trade page, waits for the first matching network response whose URL
    contains PO_CANDLES_PAT, then parses payload into {t,o,h,l,c}.
    Tune selectors/patterns via env vars without touching code.
    """
    if not PO_USER or not PO_PASS:
        raise RuntimeError("Missing PO_USER/PO_PASS env vars.")

    async with browser_context() as ctx:
        page = await ctx.new_page()

        await _login_and_open_trade(page)

        # Optional: switch symbol & interval via DOM if you have stable selectors.
        # Otherwise we just wait for the platform’s first candle payload.
        # (You can add actions here later to make sure symbol/interval match.)

        def is_candles_response(resp):
            url = resp.url or ""
            return (resp.request.resource_type == "xhr" or resp.request.resource_type == "fetch") and (PO_CANDLES_PAT in url)

        # Wait for the first candles response
        log.info("Waiting for candles network response (pattern: %s)", PO_CANDLES_PAT)
        resp = await page.wait_for_response(is_candles_response, timeout=RESP_TIMEOUT_MS)

        body = await resp.text()
        # Some PO endpoints wrap JSON in text/plain; try JSON regardless
        try:
            payload = json.loads(body)
        except Exception as e:
            # Occasionally response is an array already; try eval-like cleanup
            raise RuntimeError(f"Non-JSON or unexpected body for candles: {body[:120]}...")

        # Normalize common shapes:
        # Expect either:
        #   {"candles":[{"t":..,"o":..,"h":..,"l":..,"c":..}, ...]}
        # or direct array: [{"t":.., "o":.., ...}]
        if isinstance(payload, dict) and "candles" in payload:
            rows = payload["candles"]
        elif isinstance(payload, list):
            rows = payload
        else:
            raise RuntimeError(f"Unexpected candles payload shape: {type(payload)} keys={list(payload) if isinstance(payload, dict) else None}")

        # Map to our schema
        out = []
        for r in rows:
            t = r.get("t") or r.get("time") or r.get("timestamp")
            o = r.get("o") or r.get("open")
            h = r.get("h") or r.get("high")
            l = r.get("l") or r.get("low")
            c = r.get("c") or r.get("close")
            if t is None or o is None or h is None or l is None or c is None:
                # skip malformed
                continue
            out.append({"t": int(float(t)), "o": float(o), "h": float(h), "l": float(l), "c": float(c)})

        return out[-limit:]
