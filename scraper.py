import os
import time
from typing import List, Dict, Any, Sequence

from tenacity import retry, stop_after_attempt, wait_fixed
from playwright.async_api import async_playwright, Page, Browser

# ---- env ----
BASE_URL = os.getenv("PO_BASE_URL", "https://pocketoption.net/en/").strip()
LOGIN_EMAIL = os.getenv("PO_LOGIN_EMAIL") or os.getenv("PO_USER") or ""
LOGIN_PASSWORD = os.getenv("PO_LOGIN_PASSWORD") or os.getenv("PO_PASS") or ""
HEADLESS = os.getenv("PO_HEADLESS", "true").lower() == "true"

# ---- small helpers ----
async def _click_one_of(page: Page, selectors: Sequence[str], timeout: float = 3000) -> bool:
    for sel in selectors:
        try:
            el = page.locator(sel)
            if await el.count() > 0:
                await el.first.click(timeout=timeout)
                print(f"DEBUG: clicked {sel}")
                return True
        except Exception as e:
            print(f"DEBUG: click miss {sel}: {e}")
    return False


async def _fill_one_of(page: Page, selectors: Sequence[str], value: str, timeout: float = 3000) -> bool:
    for sel in selectors:
        try:
            el = page.locator(sel)
            if await el.count() > 0:
                await el.first.fill(value, timeout=timeout)
                print(f"DEBUG: filled {sel}")
                return True
        except Exception as e:
            print(f"DEBUG: fill miss {sel}: {e}")
    return False


@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
async def _login(page: Page) -> None:
    if not LOGIN_EMAIL or not LOGIN_PASSWORD:
        raise RuntimeError("PO_LOGIN_EMAIL/PO_LOGIN_PASSWORD not set")

    print("DEBUG: navigating to base_url:", BASE_URL)
    await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)

    # Cookie banners vary a lot; best effort
    await _click_one_of(page, [
        "button:has-text('Accept')",
        "button:has-text('I agree')",
        "button:has-text('Allow all')",
        "text=Accept all",
    ], timeout=2000)

    # Try open login dialog or move to login page
    opened = await _click_one_of(page, [
        "a[href*='login']",
        "a:has-text('Sign in')",
        "button:has-text('Log in')",
        "text=Login",
        "text=Sign in",
    ], timeout=3000)

    if not opened:
        # Fallback: go straight to known login paths
        for path in ("en/login", "login", "signin", "en/signin"):
            url = BASE_URL.rstrip("/") + "/" + path
            print("DEBUG: fallback goto", url)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                opened = True
                break
            except Exception as e:
                print("DEBUG: fallback failed:", e)

    if not opened:
        raise RuntimeError("Login entry not found")

    ok_email = await _fill_one_of(page, [
        "input[type='email']",
        "input[name='email']",
        "input[placeholder*='email' i]",
        "input[autocomplete='username']",
    ], LOGIN_EMAIL)

    ok_pass = await _fill_one_of(page, [
        "input[type='password']",
        "input[name='password']",
        "input[placeholder*='password' i]",
        "input[autocomplete='current-password']",
    ], LOGIN_PASSWORD)

    if not ok_email or not ok_pass:
        raise RuntimeError("Login inputs not found")

    clicked = await _click_one_of(page, [
        "button:has-text('Log in')",
        "button:has-text('Sign in')",
        "button[type='submit']",
        "text=Login",
    ], timeout=4000)

    if not clicked:
        raise RuntimeError("Login submit not found")

    print("DEBUG: waiting for post-login UI")
    # Heuristic: user menu or trading layout
    try:
        await page.wait_for_selector("text=Trade", timeout=15000)
    except Exception:
        # Don’t fail yet—some locales use different text
        pass


async def _open_chart(page: Page, symbol: str, interval: str) -> None:
    """
    Minimal stub to land on chart for the given symbol/interval.
    Adjust selectors to your account’s UI if needed.
    """
    print(f"DEBUG: opening chart for {symbol} @ {interval}")
    # Try a global search or symbol switcher if present
    opened = await _click_one_of(page, [
        "[data-name='asset-selector']",
        "button:has-text('Assets')",
        "button:has-text('Pairs')",
        "text=Assets",
    ], timeout=3000)

    if opened:
        await _fill_one_of(page, [
            "input[placeholder*='search' i]",
            "input[type='search']",
        ], symbol)
        await _click_one_of(page, [f"text={symbol}"], timeout=3000)

    # Interval / timeframe (very UI dependent)
    await _click_one_of(page, [
        "button:has-text('Timeframe')",
        "[data-name='tf']",
        "text=Timeframe",
    ], timeout=2000)

    await _click_one_of(page, [
        f"text={interval}",
        f"button:has-text('{interval}')",
    ], timeout=2000)


async def _read_candles_from_dom(page: Page, limit: int) -> List[Dict[str, Any]]:
    """
    Placeholder extractor: try to read last N candles from a canvas/DOM.
    Replace with a robust extraction that suits your layout.
    For now, emit synthetically changing data so your pipeline keeps moving.
    """
    print("DEBUG: extracting candles (placeholder)")
    now = int(time.time() // 60 * 60)
    out: List[Dict[str, Any]] = []
    for i in range(limit, 0, -1):
        t = now - i * 60
        base = 1.071 + i * 0.00001
        out.append({
            "t": t,
            "o": round(base, 5),
            "h": round(base + 0.00015, 5),
            "l": round(base - 0.00015, 5),
            "c": round(base + 0.00005, 5),
        })
    return out


async def fetch_candles_async(symbol: str, interval: str, limit: int) -> List[Dict[str, Any]]:
    """
    Main entry used by FastAPI. Must remain async.
    """
    print(f"DEBUG: fetch_candles_async start (headless={HEADLESS})")
    from asyncio import wait_for, TimeoutError as ATimeout

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=HEADLESS, args=["--no-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Keep each major stage bounded to avoid silent hangs
            await wait_for(_login(page), timeout=35)
            await wait_for(_open_chart(page, symbol, interval), timeout=15)
            candles = await wait_for(_read_candles_from_dom(page, limit), timeout=10)
            return candles
        except ATimeout as e:
            raise RuntimeError(f"stage timeout: {e}")
        finally:
            await context.close()
            await browser.close()