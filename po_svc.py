# po_svc.py
import os
import time
import random
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

app = FastAPI(title="PO OTC Candles Svc")
auth = HTTPBearer(auto_error=False)

# Config via env
MOCK = os.getenv("PO_MOCK", "false").lower() == "true"
SVC_TOKEN = os.getenv("PO_SVC_TOKEN")  # if set, /po/candles requires this bearer token


def _playwright_ready() -> bool:
    """
    Return True if the Playwright python package is importable.
    (Browsers come from the base image; this is a lightweight check.)
    """
    try:
        import playwright  # noqa: F401
        return True
    except Exception:
        return False


@app.get("/")
def root() -> Dict[str, bool]:
    """Simple probe that Render hits with HEAD/GET during warmup."""
    return {"ok": True}


@app.get("/healthz")
def healthz() -> Dict[str, bool]:
    """No I/O here. Purely reports flags so health stays fast and reliable."""
    return {"ok": True, "mock": MOCK, "playwright": _playwright_ready()}


def _require_token(creds: Optional[HTTPAuthorizationCredentials]) -> bool:
    """
    Enforce bearer token if PO_SVC_TOKEN is set.
    If PO_SVC_TOKEN is not set, the endpoint is open (useful for quick testing).
    """
    if SVC_TOKEN:
        if not creds or creds.scheme.lower() != "bearer" or creds.credentials != SVC_TOKEN:
            raise HTTPException(status_code=401, detail="Unauthorized")
    return True


@app.get("/po/candles")
def po_candles(
    symbol: str,
    interval: str = "1m",
    limit: int = 3,
    _: bool = Depends(_require_token),
) -> List[Dict]:
    """
    Return [{t,o,h,l,c}, ...] candles.
    - If PO_MOCK=true -> return a small changing mock series (for wiring tests).
    - Otherwise -> use scraper.fetch_candles (provided by scraper.py).
    """
    if limit <= 0 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")

    if MOCK:
        # Changing mock: generates plausible values so you can test the whole pipeline
        t0 = int(time.time() // 60 * 60)
        out: List[Dict] = []
        p = 1.0712
        for i in range(limit):
            d = random.uniform(-0.00025, 0.00025)
            o = round(p, 6)
            h = round(p + abs(d), 6)
            l = round(p - abs(d), 6)
            c = round(p + d / 2, 6)
            out.append({"t": t0 + i * 60, "o": o, "h": h, "l": l, "c": c})
            p = c
        return out

    # Real mode — call Playwright scraper
    try:
        from scraper import fetch_candles  # your async Playwright wrapper (sync facade)
    except Exception as e:
        # scraper.py missing or import error -> 501 is appropriate for "not implemented"
        raise HTTPException(status_code=501, detail=f"Real scraper not available: {e}")

    try:
        data = fetch_candles(symbol, interval, limit)
        # Basic sanity: must be list[dict] with required keys
        if not isinstance(data, list) or not all(
            isinstance(x, dict) and {"t", "o", "h", "l", "c"} <= set(x.keys())
            for x in data
        ):
            raise ValueError("scraper returned unexpected structure")
        return data
    except HTTPException:
        raise
    except Exception as e:
        # Bubble up readable error for logs/curl
        raise HTTPException(status_code=500, detail=f"scraper error: {e}")