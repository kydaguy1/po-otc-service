# scraper.py
import asyncio
from typing import List, Dict, Optional

from playwright.async_api import async_playwright, TimeoutError as PWTimeout


async def _login(page, email: str, password: str):
    # Navigate to login; support both /en/ and /en/en/login fallback
    await page.goto("/", wait_until="domcontentloaded")
    # Try common login entry points
    locators = [
        "text=Log in",
        "text=Login",
        "a[href*='login']",
        "button:has-text('Log in')",
        "button:has-text('Login')",
    ]
    for sel in locators:
        try:
            btn = page.locator(sel)
            if await btn.count() > 0:
                await btn.first.click()
                break
        except PWTimeout:
            pass

    # Fill credentials (try multiple selectors to be robust)
    email_fields = [
        "input[type='email']",
        "input[name='email']",
        "input[placeholder*='email' i]",
        "input[name='username']",
        "input[type='text']",
    ]
    pass_fields = [
        "input[type='password']",
        "input[name='password']",
        "input[placeholder*='password' i]",
    ]
    login_buttons = [
        "button[type='submit']",
        "button:has-text('Log in')",
        "button:has-text('Login')",
        "text=Sign in",
        "text=Log in",
    ]

    # Fill email
    for sel in email_fields:
        if await page.locator(sel).count():
            await page.fill(sel, email)
            break
    # Fill password
    for sel in pass_fields:
        if await page.locator(sel).count():
            await page.fill(sel, password)
            break
    # Click login
    for sel in login_buttons:
        if await page.locator(sel).count():
            await page.locator(sel).first.click()
            break

    # Wait for post-login indicator (adjust as needed)
    # If the site redirects back to /en/, networkidle is a decent proxy
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except PWTimeout:
        # Continue; not fatal — some pages stream forever
        pass


async def _extract_candles_from_page(page, symbol: str, interval: str, limit: int) -> List[Dict]:
    """
    Example extraction stub.
    This tries a few obvious patterns. If none work, it raises so the service
    returns a clear 500 instead of hanging.
    """
    # If there's a global JS object or embedded TradingView, you could evaluate it.
    # The following is a conservative placeholder — adapt for the site you see.
    js_snippet = """
    () => {
      // Try to find any candle-like structures in window variables
      const walk = (obj, depth=0) => {
        if (!obj || depth > 3) return [];
        const out = [];
        if (Array.isArray(obj) && obj.length && typeof obj[0] === 'object') {
          const sample = obj[0];
          if (['t','o','h','l','c'].every(k => k in sample)) {
            return obj;
          }
        }
        for (const k of Object.keys(obj)) {
          try {
            const v = obj[k];
            if (v && typeof v === 'object') {
              const r = walk(v, depth+1);
              if (r && r.length) return r;
            }
          } catch {}
        }
        return [];
      };
      try {
        const found = walk(window);
        return found.slice(-300); // cap
      } catch (e) {
        return [];
      }
    }
    """
    data = await page.evaluate(js_snippet)
    if isinstance(data, list) and data:
        # Clip to requested limit
        return data[-limit:]

    # If nothing found, fail clearly
    raise RuntimeError("Unable to locate candle data on page")


async def fetch_candles(
    symbol: str,
    interval: str,
    limit: int,
    base_url: str,
    headless: bool,
    email: str,
    password: str,
    logger=None,
) -> List[Dict]:
    """
    Main entry called by FastAPI. Must be async (NO asyncio.run here).
    Returns list of dicts: {t,o,h,l,c}
    """
    base = base_url.rstrip("/")  # e.g. https://pocketoption.net/en
    if logger:
        logger.info("scraper:navigating to %s/", base)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            base_url=base,
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        try:
            # 1) Login
            await _login(page, email=email, password=password)

            # 2) Navigate to trading/home where candles are present
            # (If a specific URL is required, replace the below with it)
            try:
                await page.goto("/", wait_until="domcontentloaded", timeout=20000)
            except PWTimeout:
                pass

            # 3) Extract
            candles = await _extract_candles_from_page(page, symbol, interval, limit)

            # Basic validation/normalization
            out: List[Dict] = []
            for row in candles[-limit:]:
                t = int(row.get("t"))
                o = float(row.get("o"))
                h = float(row.get("h"))
                l = float(row.get("l"))
                c = float(row.get("c"))
                out.append({"t": t, "o": o, "h": h, "l": l, "c": c})

            return out

        finally:
            await context.close()
            await browser.close()