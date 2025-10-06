# scraper.py
import os
import json
from typing import List, Dict, Any, Optional

from tenacity import retry, stop_after_attempt, wait_fixed
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

PO_MOCK = os.getenv("PO_MOCK", "false").lower() == "true"
BASE_URL = os.getenv("PO_BASE_URL", "https://pocketoption.net/en/").strip()
LOGIN_EMAIL = os.getenv("PO_LOGIN_EMAIL", "").strip()
LOGIN_PASSWORD = os.getenv("PO_LOGIN_PASSWORD", "").strip()
HEADLESS = os.getenv("PO_HEADLESS", "true").lower() == "true"

def _safe_log(msg: str) -> None:
    # never log secrets
    print(f"INFO:scraper:{msg}")

async def _click_one_of(page: Page, selectors: List[str], timeout: int = 3000) -> bool:
    for s in selectors:
        try:
            await page.locator(s).first.wait_for(state="visible", timeout=timeout)
            await page.locator(s).first.click(timeout=timeout)
            return True
        except Exception:
            pass
    return False

async def _fill_one_of(page: Page, selectors: List[str], value: str, timeout: int = 3000) -> bool:
    for s in selectors:
        try:
            await page.locator(s).first.wait_for(state="visible", timeout=timeout)
            await page.locator(s).first.fill(value, timeout=timeout)
            return True
        except Exception:
            pass
    return False

@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
async def _login(page: Page) -> None:
    if not LOGIN_EMAIL or not LOGIN_PASSWORD:
        raise RuntimeError("PO_LOGIN_EMAIL/PO_LOGIN_PASSWORD not set")

    _safe_log(f"navigating to {BASE_URL}")
    await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)

    # Try to open login view (or just go straight to /login)
    opened = await _click_one_of(page, [
        "a[href*='login']",
        "button:has-text('Log in')",
        "button:has-text('Sign in')",
        "text=Login",
        "text=Sign in",
    ], timeout=4000)

    if not opened:
        login_url = BASE_URL.rstrip("/") + "/en/login"
        _safe_log(f"fallback goto {login_url}")
        await page.goto(login_url, wait_until="domcontentloaded", timeout=20000)

    ok_email = await _fill_one_of(page, [
        "input[name='email']",
        "input[id*='email']",
        "input[type='email']",
        "input[type='text']"
    ], LOGIN_EMAIL, timeout=5000)

    ok_pass = await _fill_one_of(page, [
        "input[name='password']",
        "input[id*='pass']",
        "input[type='password']"
    ], LOGIN_PASSWORD, timeout=5000)

    if not ok_email or not ok_pass:
        raise RuntimeError("Login inputs not found")

    clicked = await _click_one_of(page, [
        "button[type='submit']",
        "button:has-text('Login')",
        "button:has-text('Sign in')",
        "text=Log in"
    ], timeout=6000)

    if not clicked:
        raise RuntimeError("Login submit not found")

    # Wait for a simple post-login signal (adjust if needed)
    try:
        await page.wait_for_selector("text=Trade", timeout=15000)
    except Exception:
        # Not fatal: site might use different post-login marker. Give it a little idle.
        await page.wait_for_timeout(3000)

async def _ensure_logged_context(browser: Browser) -> BrowserContext:
    context = await browser.new_context(viewport={"width": 1366, "height": 820})
    page = await context.new_page()
    await _login(page)
    return context

async def _mock_candles(symbol: str, interval: str, limit: int) -> List[Dict[str, Any]]:
    # simple moving values
    import time, random
    now = int(time.time() // 60 * 60)
    out = []
    price = 1.07100
    for i in range(limit):
        t = now - (limit - 1 - i) * 60
        o = price + random.uniform(-0.0002, 0.0002)
        h = o + random.uniform(0.00005, 0.00025)
        l = o - random.uniform(0.00005, 0.00025)
        c = o + random.uniform(-0.0002, 0.0002)
        out.append({"t": t, "o": round(o, 5), "h": round(h, 5), "l": round(l, 5), "c": round(c, 5)})
        price = c
    return out

async def fetch_candles(symbol: str, interval: str, limit: int) -> List[Dict[str, Any]]:
    """
    Main entry used by FastAPI route. Returns a list of {t,o,h,l,c}.
    """
    if PO_MOCK:
        return await _mock_candles(symbol, interval, limit)

    _safe_log(f"fetch_candles: {symbol} {interval} limit={limit} headless={HEADLESS}")
    async with async_playwright() as p:
        # Chromium is available in the Playwright docker image
        browser = await p.chromium.launch(headless=HEADLESS, args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            context = await _ensure_logged_context(browser)
            page = await context.new_page()

            # TODO: navigate to instrument + timeframe. This is site-specific.
            # For now, demonstrate a placeholder that waits and returns mock-ish values
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(1200)

            # Replace this block with actual DOM scraping when you know selectors
            data = await _mock_candles(symbol, interval, limit)
            return data

        finally:
            try:
                await browser.close()
            except Exception:
                pass