# scraper.py
import os
import time
from typing import List, Dict

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

PO_BASE_URL = os.getenv("PO_BASE_URL", "https://pocketoption.com")
PO_USER = os.getenv("PO_USER", "")
PO_PASS = os.getenv("PO_PASS", "")
HEADLESS = os.getenv("PO_HEADLESS", "true").lower() == "true"

LOGIN_TIMEOUT_MS = 25_000
NAV_TIMEOUT_MS = 25_000

def _now_minute() -> int:
    return int(time.time() // 60) * 60

async def _login(page):
    # 1) open site
    await page.goto(PO_BASE_URL, timeout=NAV_TIMEOUT_MS)

    # 2) click login, fill, submit
    # TODO: adjust these selectors to the current site
    await page.click("text=Log in", timeout=LOGIN_TIMEOUT_MS)
    await page.fill("input[type=email]", PO_USER, timeout=LOGIN_TIMEOUT_MS)
    await page.fill("input[type=password]", PO_PASS, timeout=LOGIN_TIMEOUT_MS)
    await page.click("button:has-text('Log in')", timeout=LOGIN_TIMEOUT_MS)

    # 3) wait for something that means “logged in”
    # TODO: replace with a reliable dashboard selector
    await page.wait_for_selector("css=[data-qa='dashboard-ready']", timeout=LOGIN_TIMEOUT_MS)

async def _open_symbol_chart(page, symbol: str):
    # Navigate to OTC symbol’s chart page
    # TODO: if there’s a direct URL, use it; otherwise open the search/symbol switcher
    # Example pseudo-flow:
    # await page.click("button[data-qa='symbol-search']")
    # await page.fill("input[data-qa='symbol-input']", symbol)
    # await page.click(f"text='{symbol}'")
    # await page.wait_for_selector("css=[data-qa='chart-ready']")
    pass

async def _read_last_n_candles(page, limit: int, interval: str) -> List[Dict]:
    # Read candles from DOM or a network response table, depending on the app.
    # Two options:
    #  A) read DOM rows
    #  B) intercept a known XHR (preferred if available)

    # --- DOM example (replace selectors) ---
    # rows = page.locator("css=[data-qa='candle-row']").last(limit)
    # out = []
    # for i in range(rows.count()):
    #     row = rows.nth(i)
    #     t = int(await row.get_attribute("data-ts"))          # or parse text
    #     o = float(await row.locator("[data-c='o']").text_content())
    #     h = float(await row.locator("[data-c='h']").text_content())
    #     l = float(await row.locator("[data-c='l']").text_content())
    #     c = float(await row.locator("[data-c='c']").text_content())
    #     out.append({"t": t, "o": o, "h": h, "l": l, "c": c})
    # return out[-limit:]

    # Placeholder until selectors are known:
    raise NotImplementedError("Hook up chart selectors or XHR capture for candles.")

async def fetch_candles(symbol: str, interval: str, limit: int) -> List[Dict]:
    if not PO_USER or not PO_PASS:
        raise RuntimeError("PO_USER/PO_PASS not set")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=HEADLESS, args=["--no-sandbox"])
        context = await browser.new_context()  # consider persistent auth later
        page = await context.new_page()

        try:
            await _login(page)
            await _open_symbol_chart(page, symbol)
            candles = await _read_last_n_candles(page, limit, interval)

            # Normalize/validate
            if not isinstance(candles, list) or not candles:
                raise RuntimeError("No candles extracted")
            for c in candles:
                if not all(k in c for k in ("t", "o", "h", "l", "c")):
                    raise RuntimeError("Bad candle shape")
                c["t"] = int(c["t"])

            return candles[-limit:]

        except PWTimeout as e:
            raise RuntimeError(f"Playwright timeout: {e}") from e
        finally:
            await context.close()
            await browser.close()
