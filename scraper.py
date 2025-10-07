# scraper.py
import os
import time
from typing import List, Dict, Any, Optional
from tenacity import retry, wait_fixed, stop_after_attempt
from loguru import logger

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

PO_BASE_URL = os.getenv("PO_BASE_URL", "https://pocketoption.net/en/")
PO_HEADLESS = os.getenv("PO_HEADLESS", "true").lower() == "true"
PO_USER = os.getenv("PO_LOGIN_EMAIL") or os.getenv("PO_USER") or ""
PO_PASS = os.getenv("PO_LOGIN_PASSWORD") or os.getenv("PO_PASS") or ""

def _login_if_needed(page: Page) -> None:
    """
    Best-effort login flow. If already logged-in or PO doesn’t require it, this just returns.
    """
    try:
        if "pocketoption" not in page.url:
            page.goto(PO_BASE_URL, wait_until="domcontentloaded", timeout=30000)

        # If we are bounced to a login page, do a simple login
        if "/login" in page.url or "log" in page.url:
            logger.info("Login page detected — attempting login")
            # The selectors below are heuristic; adjust if PO changes markup.
            email_sel = "input[type='email'], input[name='email'], #email"
            pass_sel = "input[type='password'], input[name='password'], #password"
            submit_sel = "button:has-text('Log in'), button[type='submit'], [data-test='login-submit']"

            page.locator(email_sel).first.fill(PO_USER, timeout=15000)
            page.locator(pass_sel).first.fill(PO_PASS, timeout=15000)
            page.locator(submit_sel).first.click(timeout=15000)
            page.wait_for_load_state("networkidle", timeout=30000)
    except Exception as e:
        logger.warning(f"Login step skipped/failed: {e}")

def _grab_3_fake_candles() -> List[Dict[str, Any]]:
    """
    Fallback mock (used only if you explicitly set PO_MOCK=true elsewhere).
    """
    now = int(time.time())
    base = 1.0713
    return [
        {"t": now - 120, "o": base, "h": base + 0.0002, "l": base - 0.0002, "c": base - 0.00005},
        {"t": now -  60, "o": base, "h": base + 0.00015, "l": base - 0.00025, "c": base + 0.00012},
        {"t": now      , "o": base, "h": base + 0.00012, "l": base - 0.00018, "c": base + 0.00002},
    ]

def _navigate_to_symbol(page: Page, symbol: str) -> None:
    """
    Navigate to the symbol’s chart page. Adjust URL/flow as needed if PO changes.
    """
    # Try a direct path first (update if your flow differs)
    page.goto(PO_BASE_URL, wait_until="domcontentloaded", timeout=30000)
    _login_if_needed(page)

    # Heuristic: open the trading terminal if found
    try:
        # e.g., a menu or a link leading to terminal
        if page.locator("a:has-text('Trade'), a[href*='terminal']").first.is_visible(timeout=5000):
            page.locator("a:has-text('Trade'), a[href*='terminal']").first.click()
            page.wait_for_load_state("networkidle", timeout=30000)
    except Exception:
        pass

    # If the site has a symbol search, try it (selectors may need to be adapted)
    try:
        search = page.locator("input[placeholder*='Search'], input[type='search']").first
        if search.is_visible(timeout=5000):
            search.fill(symbol)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1200)
    except Exception:
        pass

def _extract_candles_from_dom(page: Page, limit: int) -> List[Dict[str, Any]]:
    """
    Example extraction. Replace with the actual PO DOM or API that renders candles on the page.
    """
    # If PO exposes candles in a JS var or on the DOM, parse it here.
    # This demo just returns mock shaped like real.
    return _grab_3_fake_candles()[-limit:]

@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
def fetch_candles(symbol: str, interval: str = "1m", limit: int = 3) -> List[Dict[str, Any]]:
    """
    Launches a Chromium instance and returns recent candles.
    """
    logger.info(f"scraper:fetch_candles: {symbol} {interval} limit={limit} headless={PO_HEADLESS}")
    with sync_playwright() as pw:
        browser: Browser = pw.chromium.launch(headless=PO_HEADLESS)
        context: BrowserContext = browser.new_context()
        page: Page = context.new_page()

        try:
            _navigate_to_symbol(page, symbol)
            candles = _extract_candles_from_dom(page, limit)
            return candles
        finally:
            context.close()
            browser.close()