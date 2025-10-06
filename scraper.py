# scraper.py
import os
import re
import time
from typing import List, Dict

from tenacity import retry, stop_after_attempt, wait_fixed
from playwright.async_api import async_playwright, TimeoutError as PWTimeout


# --- env / config
BASE_URL = os.getenv("PO_BASE_URL", "https://pocketoption.net/en/").strip()
HEADLESS = os.getenv("PO_HEADLESS", "true").lower() == "true"
LOGIN_EMAIL = os.getenv("PO_LOGIN_EMAIL") or os.getenv("PO_USER") or ""
LOGIN_PASSWORD = os.getenv("PO_LOGIN_PASSWORD") or os.getenv("PO_PASS") or ""


def _require_creds():
    if not LOGIN_EMAIL or not LOGIN_PASSWORD:
        raise RuntimeError("PO_LOGIN_EMAIL/PO_LOGIN_PASSWORD not set")


# --- tiny helpers
async def _click_one_of(page, selectors: List[str], timeout: int = 4000) -> bool:
    for sel in selectors:
        try:
            await page.click(sel, timeout=timeout)
            return True
        except Exception:
            pass
    return False


async def _fill_one_of(page, selectors: List[str], value: str, timeout: int = 4000) -> bool:
    for sel in selectors:
        try:
            await page.fill(sel, value, timeout=timeout)
            return True
        except Exception:
            pass
    return False


# --- login flow (best-effort, resilient selectors)
@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
async def _login(page) -> None:
    # Accept cookies if present
    await _click_one_of(
        page,
        [
            'button:has-text("Accept")',
            'button:has-text("Agree")',
            'button[aria-label*="accept" i]',
        ],
        timeout=2000,
    )

    # Open login/sign-in form
    opened = await _click_one_of(
        page,
        [
            'a[href*="login"]',
            'a[href*="signin"]',
            'a[href*="auth"]',
            'button:has-text("Log in")',
            'button:has-text("Login")',
            'button:has-text("Sign in")',
            'text=Log in',
            'text=Sign in',
        ],
        timeout=4000,
    )
    if not opened:
        # Sometimes the site loads a second-level app shell
        # Try a gentle refresh once to surface the auth button.
        await page.reload(wait_until="domcontentloaded")
        opened = await _click_one_of(
            page,
            [
                'a[href*="login"]',
                'a[href*="signin"]',
                'a[href*="auth"]',
                'button:has-text("Log in")',
                'button:has-text("Sign in")',
                'text=Log in',
                'text=Sign in',
            ],
            timeout=4000,
        )
    if not opened:
        raise RuntimeError("Login/Sign-in button not found")

    # Fill credentials
    ok_email = await _fill_one_of(
        page,
        ['input[type="email"]', 'input[name="email"]', 'input[placeholder*="email" i]', 'input[name="username"]'],
        LOGIN_EMAIL,
    )
    ok_pass = await _fill_one_of(
        page,
        ['input[type="password"]', 'input[name="password"]', 'input[placeholder*="password" i]'],
        LOGIN_PASSWORD,
    )
    if not (ok_email and ok_pass):
        raise RuntimeError("Email or password field not found")

    # Submit
    submitted = await _click_one_of(
        page,
        ['button[type="submit"]', 'button:has-text("Log in")', 'button:has-text("Sign in")'],
        timeout=4000,
    )
    if not submitted:
        raise RuntimeError("Could not submit login form")

    # Wait for navigation or any post-login indicator
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except PWTimeout:
        # Not fatal—many SPAs keep connections open. Give it a moment.
        await page.wait_for_timeout(1500)


# --- fetch candles (implement your instrument navigation here)
async def _fetch_from_chart(page, symbol: str, interval: str, limit: int) -> List[Dict]:
    """
    This is a placeholder where you add the exact navigation to the chart
    and scrape candles (OHLC). For now it tries a generic pattern:
    look for an in-page candle buffer exposed by SPA, else raise.
    """
    # If your app exposes a global buffer, try to read it
    try:
        data = await page.evaluate(
            """() => {
                // Example: try to find any global with 'candles' like array
                for (const k of Object.keys(window)) {
                  try {
                    const v = window[k];
                    if (v && typeof v === 'object') {
                      if (Array.isArray(v.candles) && v.candles.length) {
                        return v.candles;
                      }
                    }
                  } catch (_) {}
                }
                return null;
            }"""
        )
        if data and isinstance(data, list):
            # map to {t,o,h,l,c}
            out = []
            for row in data[-limit:]:
                # best effort key mapping
                t = row.get("t") or row.get("time") or row.get("timestamp")
                o = row.get("o") or row.get("open")
                h = row.get("h") or row.get("high")
                l = row.get("l") or row.get("low")
                c = row.get("c") or row.get("close")
                if all(x is not None for x in (t, o, h, l, c)):
                    out.append({"t": int(t), "o": float(o), "h": float(h), "l": float(l), "c": float(c)})
            if out:
                return out[-limit:]
    except Exception:
        pass

    # If you get here, you’ll need to add page navigation/selectors specific to the site.
    raise RuntimeError("Candle source not found yet—add page navigation/selectors for your chart.")


# --- public async API (used by FastAPI)
async def fetch_candles_async(symbol: str, interval: str, limit: int) -> List[Dict]:
    """
    Main entry point used by FastAPI. Fully async—do NOT call asyncio.run() here.
    """
    _require_creds()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(locale="en-US")
        page = await context.new_page()

        await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        await _login(page)

        # TODO: If a specific route is needed to open the instrument/interval, do it here.
        # e.g., await page.goto(f"{BASE_URL}trade?asset={symbol}&tf={interval}", wait_until="domcontentloaded")

        candles = await _fetch_from_chart(page, symbol, interval, limit)

        await context.close()
        await browser.close()

        return candles