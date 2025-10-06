# po_svc.py
import os, time, random
from typing import List, Dict
from fastapi import FastAPI, Header, HTTPException, Request

app = FastAPI(title="PO OTC Candles")

# --- helpers ---------------------------------------------------------------

def _require_token(authorization: str | None) -> None:
    """Simple bearer token check using PO_SVC_TOKEN if it is set."""
    svc_token = os.getenv("PO_SVC_TOKEN", "").strip()
    if not svc_token:
        return  # open if no token configured
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1]
    if token != svc_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

def _mock_candles(symbol: str, interval: str, limit: int) -> List[Dict]:
    """
    Tiny mock generator that produces *changing* values every call.
    """
    # base around 1.071 with tiny random noise
    now = int(time.time())
    step = 60 if interval.endswith("m") else 60
    # jitter seed so consecutive calls are different
    random.seed(now ^ hash(symbol) ^ hash(interval))
    last_close = 1.0710 + random.uniform(-0.001, 0.001)
    out: List[Dict] = []
    # newest last
    for i in range(limit, 0, -1):
        ts = (now // step) * step - i * step
        o = last_close + random.uniform(-0.0002, 0.0002)
        h = max(o, o + abs(random.uniform(0.00005, 0.00025)))
        l = min(o, o - abs(random.uniform(0.00005, 0.00025)))
        c = l + (h - l) * random.random()
        out.append({"t": ts, "o": round(o, 6), "h": round(h, 6),
                    "l": round(l, 6), "c": round(c, 6)})
        last_close = c
    return out

# --- routes ----------------------------------------------------------------

@app.get("/")
def root():
    return {"ok": True}

@app.get("/healthz")
def healthz():
    return {
        "ok": True,
        "mock": os.getenv("PO_MOCK", "false").lower() == "true",
        # purely informational flags
        "playwright": os.getenv("PO_PLAYWRIGHT", "true").lower() == "true",
    }

@app.get("/po/candles")
def po_candles(
    request: Request,
    symbol: str,
    interval: str = "1m",
    limit: int = 3,
    authorization: str | None = Header(default=None),
):
    """
    GET /po/candles?symbol=EURUSD_OTC&interval=1m&limit=3

    If PO_MOCK=true -> returns synthetic candles.
    Else -> calls scraper.fetch_candles(...) (Playwright).
    """
    _require_token(authorization)

    use_mock = os.getenv("PO_MOCK", "false").lower() == "true"
    if use_mock:
        return _mock_candles(symbol, interval, max(1, min(limit, 100)))

    # real path (Playwright)
    try:
        from scraper import fetch_candles  # your real scraper
    except Exception as e:
        raise HTTPException(
            status_code=501,
            detail=f"Real scraper not wired yet: {e}. Set PO_MOCK=true until scraper is implemented."
        )

    try:
        candles = fetch_candles(symbol=symbol, interval=interval, limit=limit)
        return candles
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"scraper error: {e}")