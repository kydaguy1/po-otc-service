# po_svc.py
import os
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# <-- make sure scraper.py sits next to this file and exports fetch_candles()
from scraper import fetch_candles


# -----------------------
# Env / config
# -----------------------
PO_MOCK: bool = os.getenv("PO_MOCK", "false").lower() == "true"
PO_SVC_TOKEN: Optional[str] = os.getenv("PO_SVC_TOKEN")

# Optional flags just for visibility in /healthz
PO_HEADLESS: bool = os.getenv("PO_HEADLESS", "true").lower() == "true"
PO_BASE_URL: str = os.getenv("PO_BASE_URL", "https://pocketoption.net/en/")

# Auth (Bearer) – only enforced when PO_SVC_TOKEN is set
bearer = HTTPBearer(auto_error=False)

def require_auth(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> None:
    if not PO_SVC_TOKEN:
        # no token configured => open endpoint
        return
    if not creds or creds.scheme.lower() != "bearer" or creds.credentials != PO_SVC_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


# -----------------------
# App
# -----------------------
app = FastAPI(title="Pocket Option OTC Candles")


@app.get("/")
async def root() -> Dict[str, Any]:
    # Render probes / with HEAD; keep this lightweight & 200
    return {"ok": True}


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    # No I/O here; just reflect config
    return {
        "ok": True,
        "mock": PO_MOCK,
        "playwright": True,     # indicates we intend to use Playwright in prod
        "headless": PO_HEADLESS,
        "base_url": PO_BASE_URL,
    }


@app.get("/po/candles")
async def po_candles(
    symbol: str,
    interval: str = "1m",
    limit: int = 3,
    _auth: None = Depends(require_auth),
) -> List[Dict[str, Any]]:
    """
    Returns recent candles for a symbol.
    - If PO_MOCK=true, returns synthetic data (no Playwright needed).
    - If PO_MOCK=false, calls scraper.fetch_candles(...) and returns real data.
    """
    if PO_MOCK:
        # --- simple mock for testing wire-up ---
        import time, random
        base = 1.0710
        now = int(time.time() // 60 * 60)
        out: List[Dict[str, Any]] = []
        for i in range(limit, 0, -1):
            t = now - (i * 60)
            o = base + random.uniform(-0.0010, 0.0010)
            h = o + random.uniform(0.0001, 0.0005)
            l = o - random.uniform(0.0001, 0.0005)
            c = o + random.uniform(-0.0005, 0.0005)
            out.append({"t": t, "o": round(o, 6), "h": round(h, 6), "l": round(l, 6), "c": round(c, 6)})
        return out

    # --- real path via Playwright ---
    try:
        candles = await fetch_candles(symbol=symbol, interval=interval, limit=limit)
        return candles
    except NotImplementedError as e:
        # We reached the site but haven’t wired extraction yet.
        raise HTTPException(status_code=501, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        # Surface scraper problems as 500 with a readable message
        raise HTTPException(status_code=500, detail=f"scraper error: {e}") from e