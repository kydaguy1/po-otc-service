# scraper.py
import os
import time
from typing import List, Dict
from playwright.async_api import async_playwright

# Read env (set these in Render)
PO_LOGIN_EMAIL = os.getenv("PO_LOGIN_EMAIL", "")
PO_LOGIN_PASSWORD = os.getenv("PO_LOGIN_PASSWORD", "")
PO_BASE_URL = os.getenv("PO_BASE_URL", "https://app.pocketoption.com/en/")  # adjust to actual
PO_HEADLESS = os.getenv("PO_HEADLESS", "true").lower() == "true"

# IMPORTANT on Render native:
# In your Render "Build Command", run:   python -m playwright install chromium
# …so the chromium bundle exists at runtime. (No apt/deb is needed.)

async def _login(page):
    # TODO: Update selectors/flow to match the actual site.
    await page.goto(PO_BASE_URL, wait_until="domcontentloaded")
    # Example pseudo selectors — replace with your real ones:
    await page.click("text=Sign in")
    await page.fill("input[type=email]", PO_LOGIN_EMAIL)
    await page.fill("input[type=password]", PO_LOGIN_PASSWORD)
    await page.click("button[type=submit]")
    # wait for some authenticated indicator:
    await page.wait_for_selector("css=[data-user-logged-in]")

async def _open_chart(page, symbol: str, interval: str):
    # TODO: Navigate to the chart, set symbol + timeframe.
    # Replace this block with your real UI steps/selectors.
    # Example pseudo:
    await page.click("css=[data-open-chart]")
    await page.fill("css=[data-symbol-input]", symbol)
    await page.press("css=[data-symbol-input]", "Enter")
    await page.click(f"css=[data-interval='{interval}']")
    # ensure the candle container is visible
    await page.wait_for_selector("css=[data-candles-ready]")

async def _read_candles_from_dom(page, limit: int) -> List[Dict]:
    # TODO: Replace with your actual DOM scraping logic for OHLC.
    # Here’s a placeholder that returns synthetic candles so the flow is testable.
    now = int(time.time() // 60 * 60)
    base = 1.07100
    rows = []
    for i in range(limit):
        t = now - (limit - 1 - i) * 60
        o = base + i * 0.00011
        h = o + 0.00020
        l = o - 0.00020
        c = o + 0.00007
        rows.append({"t": t, "o": round(o, 6), "h": round(h, 6), "l": round(l, 6), "c": round(c, 6)})
    return rows

async def fetch_candles(symbol: str, interval: str, limit: int) -> List[Dict]:
    if not (PO_LOGIN_EMAIL and PO_LOGIN_PASSWORD):
        raise RuntimeError("PO_LOGIN_EMAIL/PO_LOGIN_PASSWORD not set")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=PO_HEADLESS)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        try:
            await _login(page)
            await _open_chart(page, symbol, interval)
            rows = await _read_candles_from_dom(page, limit)
            return rows
        finally:
            await ctx.close()
            await browser.close()
