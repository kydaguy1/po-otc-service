# scraper.py
import os
import time
import logging
from typing import List
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

log = logging.getLogger("scraper")

UA = os.getenv("PO_UA",
               "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

def _bool(env: str, default: bool) -> bool:
    return os.getenv(env, "true" if default else "false").lower() == "true"

@asynccontextmanager
async def browser_ctx(headless: bool):
    """
    Headless Chromium with flags that work well on Render.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        context = await browser.new_context(
            locale="en-US",
            user_agent=UA,
            viewport={"width": 1280, "height": 800},
            java_script_enabled=True,
        )

        # Stealth-ish: remove webdriver flag
        await context.add_init_script(
            """Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"""
        )

        # Some sites require referrerPolicy default
        # await context.set_extra_http_headers({"Referer": "https://pocketoption.net/en/"})

        page = await context.new_page()
        try:
            yield page
        finally:
            await context.close()
            await browser.close()

async def _goto_clean(page, url: str, timeout_ms: int = 30000):
    """
    Navigate and normalize random extra /en/en/login redirects.
    """
    log.info("navigating to %s", url)
    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    # Fix duplicate /en/en/
    url_now = page.url.replace("//en/en/", "/en/")
    if url_now != page.url:
        await page.goto(url_now, wait_until="domcontentloaded", timeout=timeout_ms)
    return page.url

async def _login(page, base_url: str, email: str, password: str):
    """
    Robust login: tries multiple common selectors and text matches.
    """
    # Ensure we’re on the login page
    if "/login" not in page.url:
        # many flows redirect from /en/ to /en/login
        if page.url.rstrip("/").endswith("/en"):
            try:
                await page.click('text="Log in"', timeout=4000)
            except PWTimeout:
                pass  # maybe already on login
        # direct to login if needed
        if "/login" not in page.url:
            login_url = base_url.rstrip("/") + "/login"
            await _goto_clean(page, login_url)

    # type email
    selectors_email = [
        'input[type="email"]',
        'input[name="email"]',
        'input[placeholder*="Email" i]',
        '#email'
    ]
    typed = False
    for sel in selectors_email:
        try:
            await page.fill(sel, email, timeout=3000)
            typed = True
            break
        except PWTimeout:
            continue
    if not typed:
        raise RuntimeError("Could not find email field")

    # type password
    selectors_pass = [
        'input[type="password"]',
        'input[name="password"]',
        'input[placeholder*="Password" i]',
        '#password'
    ]
    typed = False
    for sel in selectors_pass:
        try:
            await page.fill(sel, password, timeout=3000)
            typed = True
            break
        except PWTimeout:
            continue
    if not typed:
        raise RuntimeError("Could not find password field")

    # click login
    clicked = False
    for locator in [
        'button[type="submit"]',
        'button:has-text("Log in")',
        'text="Log in"',
        'text="Sign in"',
    ]:
        try:
            await page.click(locator, timeout=4000)
            clicked = True
            break
        except PWTimeout:
            continue
    if not clicked:
        raise RuntimeError("Could not find Login button")

    # wait for post-login landing (URL changes OR a known element appears)
    try:
        await page.wait_for_url("**/en/**", timeout=15000)
    except PWTimeout:
        # Sometimes the URL stays similar but we’re logged in—try a small wait
        await page.wait_for_timeout(2000)

async def _open_chart(page, symbol: str, interval: str):
    """
    Navigate to the trading chart for the given symbol and set timeframe.
    The exact DOM of PocketOption can change; keep selectors flexible.
    """
    # If there is a direct chart route you know, go there; otherwise, click UI.
    # Example: go to the main trade page:
    await _goto_clean(page, "https://pocketoption.net/en/")
    # Try to ensure chart visible (placeholder, adapt if you know better selectors)
    # Wait for some canvas/chart presence
    try:
        await page.wait_for_selector("canvas", timeout=12000)
    except PWTimeout:
        log.warning("Chart canvas not seen; continuing anyway")

    # Set timeframe button (1m)
    for tf_selector in [
        'button:has-text("1m")',
        'text="M1"',
        '[data-timeframe="1m"]',
    ]:
        try:
            await page.click(tf_selector, timeout=3000)
            break
        except PWTimeout:
            continue

    # TODO: choose symbol if UI allows picking EURUSD_OTC; leaving as-is
    await page.wait_for_timeout(1000)

def _fake_candles(limit: int) -> List[dict]:
    import random
    now = int(time.time()) // 60 * 60
    out = []
    last = 1.07100 + random.random() * 0.0006
    for i in range(limit, 0, -1):
        t = now - i * 60
        o = round(last, 5)
        h = round(o + 0.0002, 5)
        l = round(o - 0.0002, 5)
        c = round(o + random.uniform(-0.00015, 0.00015), 5)
        out.append({"t": t, "o": o, "h": h, "l": l, "c": c})
        last = c
    return out

async def fetch_candles(
    symbol: str,
    interval: str,
    limit: int,
    *,
    headless: bool,
    base_url: str,
    email: str,
    password: str,
    warmup_only: bool = False,
) -> List[dict]:
    """
    Logs in, opens chart, returns last `limit` candles.
    NOTE: Because PocketOption doesn't expose a public candles HTTP API,
    this demo currently returns UI-derived (or placeholder) candles.
    Replace the section marked 'EXTRACT CANDLES HERE' with your
    page.evaluate(...) logic or network interception as you refine.
    """
    base_url = base_url.rstrip("/") + "/"
    timeout_ms = 30000

    async with browser_ctx(headless=headless) as page:
        url = await _goto_clean(page, base_url, timeout_ms)
        log.info("landed on %s", url)

        # If already logged in (cookie persists within this context only),
        # skip login. Otherwise perform login.
        if "login" in page.url:
            log.info("at login page; performing login")
            await _login(page, base_url, email, password)
        else:
            # Try to detect if there is a visible "Log in" prompt
            try:
                if await page.is_visible('text="Log in"', timeout=2000):
                    await page.click('text="Log in"')
                    await _login(page, base_url, email, password)
            except Exception:
                pass

        if warmup_only:
            return []

        # Open chart and set timeframe
        await _open_chart(page, symbol, interval)

        # === EXTRACT CANDLES HERE =========================================
        # If you know how to read candles from the chart (e.g. there’s
        # a JS object on window or a network request to intercept), add it.
        # For now, return moving placeholder data so your bot continues:
        candles = _fake_candles(limit)
        # ==================================================================

        return candles