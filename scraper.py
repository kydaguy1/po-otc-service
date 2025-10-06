# scraper.py
import os, json, asyncio, time
from typing import List, Dict
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

PO_BASE_URL = os.getenv("PO_BASE_URL", "https://pocketoption.com/en/").rstrip("/")
PO_HEADLESS = os.getenv("PO_HEADLESS", "true").lower() == "true"
EMAIL = os.getenv("PO_LOGIN_EMAIL")
PASSWORD = os.getenv("PO_LOGIN_PASSWORD")

class ScraperError(RuntimeError): ...

async def _login(page):
    if not EMAIL or not PASSWORD:
        raise ScraperError("PO_LOGIN_EMAIL / PO_LOGIN_PASSWORD not set")

    # Go to landing/login
    await page.goto(PO_BASE_URL, wait_until="domcontentloaded", timeout=30000)

    # If they redirect to app.* you’ll still be fine; Playwright follows redirects.
    # Adjust selectors to whatever the site currently uses:
    # Example flow (placeholder – update to the current DOM):
    try:
        # If there’s a “Sign In” button:
        # await page.click("text=Sign in")
        # await page.fill("input[type=email]", EMAIL)
        # await page.fill("input[type=password]", PASSWORD)
        # await page.click("button:has-text('Sign in')")
        # await page.wait_for_load_state("networkidle", timeout=30000)
        pass
    except PWTimeout:
        raise ScraperError("Login flow timed out; update selectors in scraper.py")

async def _fetch_prices(page, symbol: str, interval: str, limit: int) -> List[Dict]:
    """
    Replace this logic with the real source of candle data:
    - If the site exposes an XHR/JSON endpoint, use page.route to capture or page.evaluate to fetch.
    - As a starter, we’ll just read a price every ~1s and synthesize candles so the pipeline works.
    """
    # Demo: synthesize 3 tiny candles around a moving price (replace with real scraping)
    base = time.time()
    candles = []
    price = 1.07130
    step = 0.00015
    for i in range(limit):
        o = round(price, 6)
        h = round(price + step, 6)
        l = round(price - step, 6)
        c = round(price + step/2, 6)
        candles.append({"t": int(base//60*60) + i*60, "o": o, "h": h, "l": l, "c": c})
        price += step
        await asyncio.sleep(0.2)
    return candles

async def _run(symbol: str, interval: str, limit: int) -> List[Dict]:
    # Disable a couple flags that sometimes help on PaaS
    launch_args = ["--disable-dev-shm-usage", "--disable-setuid-sandbox"]
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=PO_HEADLESS, args=launch_args)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await _login(page)
            candles = await _fetch_prices(page, symbol, interval, limit)
            return candles
        except PWTimeout as e:
            raise ScraperError(f"Timeout: {e}")
        finally:
            await context.close()
            await browser.close()

def fetch_candles(symbol: str, interval: str, limit: int) -> List[Dict]:
    try:
        return asyncio.run(_run(symbol, interval, limit))
    except ScraperError as e:
        raise
    except Exception as e:
        # bubble up with a clear message
        raise ScraperError(str(e))