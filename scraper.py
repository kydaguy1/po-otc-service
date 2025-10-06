# scraper.py
import os
import re
import asyncio
from typing import List, Dict
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, TimeoutError as PWTimeout


PO_BASE_URL = os.getenv("PO_BASE_URL", "https://pocketoption.net/en/").rstrip("/") + "/"
PO_HEADLESS = os.getenv("PO_HEADLESS", "true").lower() == "true"
PO_LOGIN_EMAIL = os.getenv("PO_LOGIN_EMAIL")
PO_LOGIN_PASSWORD = os.getenv("PO_LOGIN_PASSWORD")

_LOGIN_NAMES = re.compile(r"(log\s*in|sign\s*in|continue)", re.I)
_ACCEPT_NAMES = re.compile(r"(accept|agree|got it|allow all|ok)", re.I)


@asynccontextmanager
async def _browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=PO_HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        context = await browser.new_context(
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        # speed up: skip images/video
        await page.route("**/*", lambda r: r.abort() if r.request.resource_type in {"image", "media"} else r.continue_())

        try:
            yield page
        finally:
            await context.close()
            await browser.close()


async def _dismiss_banners(page):
    # common cookie/consent banners
    try:
        # try several visible buttons that often appear
        buttons = page.locator("button, [role=button], .btn")
        count = await buttons.count()
        for i in range(min(count, 20)):
            b = buttons.nth(i)
            try:
                txt = (await b.inner_text()).strip()
            except Exception:
                continue
            if txt and _ACCEPT_NAMES.search(txt):
                if await b.is_visible():
                    await b.click(timeout=2000)
                    break
    except Exception:
        pass


async def _go_login(page):
    # 1) try direct /login first (most reliable)
    login_urls = [
        PO_BASE_URL + "login",
        PO_BASE_URL,  # fall back to home and try to find a login trigger
    ]
    for url in login_urls:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await _dismiss_banners(page)
        except Exception:
            continue

        # If we already see an email field, we're on login page
        if await page.locator('input[type="email"], input[name*="email" i]').first.is_visible(timeout=1000).catch(lambda _: False):
            return True

        # Otherwise try clicking something like "Log in"/"Sign in" or a link to /login
        try:
            # any link that looks like login
            login_link = page.locator('a[href*="login" i], a[href*="signin" i]').first
            if await login_link.is_visible(timeout=1000):
                await login_link.click()
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                return True
        except Exception:
            pass

        try:
            # any visible button with login-ish text
            btn = page.get_by_role("button", name=_LOGIN_NAMES)
            if await btn.first.is_visible(timeout=1000):
                await btn.first.click()
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                return True
        except Exception:
            pass

    return False


async def _do_login(page):
    if not (PO_LOGIN_EMAIL and PO_LOGIN_PASSWORD):
        raise RuntimeError("PO_LOGIN_EMAIL/PO_LOGIN_PASSWORD not set")

    # Fill email/password with multiple selectors for robustness
    email_sel = 'input[type="email"], input[name*="email" i]'
    pass_sel = 'input[type="password"], input[name*="password" i]'

    await page.locator(email_sel).first.fill(PO_LOGIN_EMAIL, timeout=15000)
    await page.locator(pass_sel).first.fill(PO_LOGIN_PASSWORD, timeout=15000)

    # submit: try common submit buttons
    cand = [
        page.get_by_role("button", name=_LOGIN_NAMES).first,
        page.locator('button[type="submit"]').first,
        page.locator('input[type="submit"]').first,
        page.locator('button:has-text("Log in"), button:has-text("Sign in")').first,
    ]
    for c in cand:
        try:
            if await c.is_visible(timeout=1000):
                await c.click()
                break
        except Exception:
            continue

    await page.wait_for_load_state("networkidle", timeout=25000)


async def _navigate_to_chart(page, symbol: str):
    """
    Minimal placeholder navigation. If your app requires a specific page,
    replace this with the exact chart URL or clicks needed after login.
    """
    # In many cases, after login you land on the trading app. Ensure DOM is stable:
    await page.wait_for_load_state("networkidle", timeout=20000)

    # TODO: adjust to the page that exposes candles or use the internal API
    # For now, this function just asserts we're logged in by checking any “logout/profile” hints.
    # If needed, add locators that only exist for logged-in users.
    return True


async def fetch_candles(symbol: str, interval: str, limit: int) -> List[Dict]:
    """
    Logs in and returns a small list of candles as dicts.
    Replace the bottom “fake fetch” with your real extraction or internal API call.
    """
    async with _browser() as page:
        try:
            ok = await _go_login(page)
            if not ok:
                raise RuntimeError("Couldn't reach login page (selector mismatch).")

            await _do_login(page)
            await _navigate_to_chart(page, symbol)

            # TODO: Replace this with your real scraping logic:
            # e.g., evaluate JS to pull candles from page vars or call an internal XHR.
            # Placeholder: return an empty list to show “logged in but no data path wired”.
            raise NotImplementedError("Logged in, but candle extraction is not wired.")

        except PWTimeout as e:
            # help debugging on Render: surface the selector that timed out
            raise RuntimeError(f"playwright timeout: {e}") from e


# Convenience for manual testing locally:
if __name__ == "__main__":
    async def _t():
        print(await fetch_candles("EURUSD_OTC", "1m", 3))
    asyncio.run(_t())