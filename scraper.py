# scraper.py
# Async Playwright scraper used by po_svc.py when PO_MOCK=false
#
# Env vars (set on Render -> Environment):
#   PO_LOGIN_EMAIL        Pocket Option email (required)
#   PO_LOGIN_PASSWORD     Pocket Option password (required)
#   PO_BASE_URL           Base URL (default: https://pocketoption.net/en/)
#   PO_HEADLESS           "true"/"false" (default: true)
#   PO_TIMEOUT_MS         per-step timeout in ms (default: 30000)
#   PO_USER_AGENT         optional UA override
#
# What it does:
# - Starts Chromium with Playwright
# - Reuses a persisted storage state (/tmp/po_state.json) so you don't have
#   to log in every request
# - If not logged in, performs login using the provided credentials
# - Navigates to the app and (TODO) fetches candles for a symbol/interval
#
# NOTE: The DOM/API on Pocket Option may change. The extraction part is
#       isolated in _fetch_candles_via_page() so you can update selectors
#       without touching the plumbing.

import os
import json
import asyncio
from typing import List, Dict, Any, Optional

from playwright.async_api import async_playwright, BrowserContext, Page, TimeoutError as PWTimeoutError


# ---------- Config helpers ----------

def _boolenv(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() == "true"

def _getenv(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v is not None and v != "" else default

PO_BASE_URL     = _getenv("PO_BASE_URL", "https://pocketoption.net/en/")
PO_HEADLESS     = _boolenv("PO_HEADLESS", "true")
PO_TIMEOUT_MS   = int(_getenv("PO_TIMEOUT_MS", "30000") or "30000")
PO_USER_AGENT   = _getenv("PO_USER_AGENT", None)

PO_LOGIN_EMAIL  = _getenv("PO_LOGIN_EMAIL")
PO_LOGIN_PASS   = _getenv("PO_LOGIN_PASSWORD")

STATE_PATH      = "/tmp/po_state.json"  # reused between requests in the same instance


# ---------- Public entry point (called by po_svc.py) ----------

def fetch_candles(symbol: str, interval: str, limit: int) -> List[Dict[str, Any]]:
    """
    Synchronous entry point used by FastAPI handler.
    Wraps the async workflow safely.
    """
    return asyncio.run(_fetch_candles(symbol, interval, limit))


# ---------- Main async workflow ----------

async def _fetch_candles(symbol: str, interval: str, limit: int) -> List[Dict[str, Any]]:
    # Pre-flight validation
    if not PO_LOGIN_EMAIL or not PO_LOGIN_PASS:
        raise RuntimeError("PO_LOGIN_EMAIL / PO_LOGIN_PASSWORD not set")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=PO_HEADLESS)
        context = await _new_context(browser)
        page = await context.new_page()

        try:
            await _warm(page)  # open base URL and ensure we’re logged in
            candles = await _fetch_candles_via_page(page, symbol, interval, limit)
            if not isinstance(candles, list):
                raise RuntimeError("Unexpected candles type (not a list)")
            # Basic shape validation
            for c in candles:
                for k in ("t", "o", "h", "l", "c"):
                    if k not in c:
                        raise RuntimeError(f"Bad candle missing '{k}': {c}")
            return candles
        finally:
            # Persist storage so future requests skip login
            try:
                await context.storage_state(path=STATE_PATH)
            except Exception:
                pass
            await context.close()
            await browser.close()


# ---------- Browser helpers ----------

async def _new_context(browser) -> BrowserContext:
    args = {}
    if PO_USER_AGENT:
        args["user_agent"] = PO_USER_AGENT

    # Reuse prior login if storage file exists
    if os.path.exists(STATE_PATH):
        args["storage_state"] = STATE_PATH

    context = await browser.new_context(**args)
    context.set_default_timeout(PO_TIMEOUT_MS)
    return context


async def _warm(page: Page) -> None:
    """
    Ensure we can reach base URL and are logged in.
    We handle both pocketoption.net and app.pocketoption.com, plus consent banners.
    """
    # Normalize base url (ensure trailing slash)
    base = PO_BASE_URL if PO_BASE_URL.endswith("/") else PO_BASE_URL + "/"

    # Step 1: load base and handle consent/redirects
    await page.goto(base, wait_until="domcontentloaded")
    await _dismiss_consent(page)

    # Step 2: detect whether we are already logged in
    if await _is_logged_in(page):
        return

    # Step 3: go to login page and authenticate
    await _perform_login(page)


async def _dismiss_consent(page: Page) -> None:
    """Try to dismiss any cookie/privacy banners if present."""
    candidates = [
        "button:has-text('Accept')",
        "button:has-text('I agree')",
        "button:has-text('Allow all')",
        "[data-testid='cookie-accept']",
    ]
    for sel in candidates:
        try:
            await page.locator(sel).first.click(timeout=2000)
            break
        except PWTimeoutError:
            continue
        except Exception:
            continue


async def _is_logged_in(page: Page) -> bool:
    """
    Heuristic: if we can see a user/avatar/menu or a logout entry, consider logged in.
    Fall back to checking the presence of a login button.
    """
    probes_logged = [
        "text=Logout",
        "a[href*='logout']",
        "[data-testid='user-avatar']",
        "nav :text('Profile')",
    ]
    for sel in probes_logged:
        try:
            if await page.locator(sel).first.is_visible():
                return True
        except Exception:
            pass

    probes_login = [
        "text=Log in",
        "text=Sign in",
        "button:has-text('Log in')",
        "a[href*='login']",
    ]
    for sel in probes_login:
        try:
            if await page.locator(sel).first.is_visible():
                return False
        except Exception:
            pass

    # As a fallback, assume not logged in (we’ll try login)
    return False


async def _perform_login(page: Page) -> None:
    """
    Try a few common login layouts:
      - A dedicated login page
      - A “Log in” button that opens a modal
    """
    # 1) Click any login/sign in control if visible
    openers = [
        "a:has-text('Log in')",
        "a:has-text('Sign in')",
        "button:has-text('Log in')",
        "button:has-text('Sign in')",
        "a[href*='login']",
    ]
    for sel in openers:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible():
                await loc.click()
                break
        except Exception:
            pass

    # 2) Fill typical fields (try common name/id patterns)
    email_fields = [
        "input[name='email']",
        "input[type='email']",
        "#email",
        "input[autocomplete='username']",
    ]
    pass_fields = [
        "input[name='password']",
        "input[type='password']",
        "#password",
        "input[autocomplete='current-password']",
    ]
    submit_buttons = [
        "button[type='submit']",
        "button:has-text('Log in')",
        "button:has-text('Sign in')",
        "input[type='submit']",
    ]

    # Focus & type email
    for sel in email_fields:
        try:
            await page.locator(sel).first.fill(PO_LOGIN_EMAIL, timeout=5000)
            break
        except Exception:
            continue
    else:
        raise RuntimeError("Could not locate email field on login form")

    # Focus & type password
    for sel in pass_fields:
        try:
            await page.locator(sel).first.fill(PO_LOGIN_PASS, timeout=5000)
            break
        except Exception:
            continue
    else:
        raise RuntimeError("Could not locate password field on login form")

    # Click submit
    for sel in submit_buttons:
        try:
            await page.locator(sel).first.click(timeout=5000)
            break
        except Exception:
            continue

    # Wait for navigation / logged-in indicator
    try:
        # Either navigation (url change) or a visible user element
        await page.wait_for_load_state("networkidle", timeout=PO_TIMEOUT_MS)
    except PWTimeoutError:
        # Not always fatal; continue and re-check login
        pass

    if not await _is_logged_in(page):
        # Capture an informative error
        html = await page.content()
        raise RuntimeError("Login appears to have failed; update selectors.\n"
                           "TIP: set PO_HEADLESS=false and try again to see what the page shows.")


# ---------- Data extraction (update this for the site) ----------

async def _fetch_candles_via_page(page: Page, symbol: str, interval: str, limit: int) -> List[Dict[str, Any]]:
    """
    This is the *only* place you’ll likely need to tweak when the site changes.
    Strategy:
      - We run a small JS snippet inside the page that performs a fetch() to
        whatever endpoint your app uses to retrieve candles.
      - If the site doesn’t expose a fetchable endpoint (CORS/opaque), replace
        this with DOM scraping logic instead.

    Return format: list of {t, o, h, l, c} with:
      t: epoch seconds (int)
      o,h,l,c: floats
    """
    # --- EXAMPLE (placeholder) ---
    # Replace the URL/path & parameters with the site’s real candle endpoint,
    # or rewrite to scrape from DOM elements.
    # If you don’t know the endpoint yet, temporarily return a hardcoded list
    # and iterate in headed mode to find the right call.

    js = """
    async (symbol, interval, limit) => {
      // TODO: Replace with the app's real candle source.
      // This placeholder just returns fake-looking but changing candles.
      const now = Math.floor(Date.now()/1000);
      const out = [];
      for (let i = limit - 1; i >= 0; i--) {
        const t = now - i * 60;
        const base = 1.071 + (Math.sin(t/180) * 0.0008);
        const o = +(base).toFixed(5);
        const h = +(base + 0.0006).toFixed(5);
        const l = +(base - 0.0006).toFixed(5);
        const c = +(base + (Math.random()-0.5)*0.0005).toFixed(5);
        out.push({ t, o, h, l, c });
      }
      return out;
    }
    """

    candles = await page.evaluate(js, symbol, interval, int(limit))
    return candles