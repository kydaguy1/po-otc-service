"""
Service helpers for PocketOption OTC candle proxy.

This module centralizes:
- token verification (PO_SVC_TOKEN)
- the list of supported OTC symbols
- a simple 'fetch_candles' that returns PO-shaped JSON
- (optional) upstream passthrough (PO_UPSTREAM_URL), if you have a separate
  scraper/gateway. If PO_UPSTREAM_URL is unset, you can plug your own local
  fetcher here.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

import httpx
from fastapi import HTTPException

# ----- Configuration from env -----
PO_SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "")
PO_UPSTREAM_URL = os.getenv("PO_UPSTREAM_URL", "").rstrip("/")  # e.g. https://your-upstream.app

# A sane default list. Add/remove to taste.
OTC_SYMBOLS: List[str] = [
    # majors (OTC)
    "EURUSD_OTC", "GBPUSD_OTC", "USDJPY_OTC", "USDCHF_OTC", "USDCAD_OTC", "AUDUSD_OTC", "NZDUSD_OTC",
    # crosses & regionals (common ones)
    "EURJPY_OTC", "EURGBP_OTC", "EURAUD_OTC", "GBPAUD_OTC", "GBPJPY_OTC", "AUDJPY_OTC", "CADJPY_OTC",
]

# ----- Security -----
def verify_token(token: Optional[str]) -> None:
    """
    Raises 401 if token missing or mismatched.
    """
    if not PO_SVC_TOKEN:
        raise HTTPException(status_code=500, detail="Service misconfigured: PO_SVC_TOKEN is empty")
    if not token or token != PO_SVC_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ----- Metadata -----
def list_symbols() -> Dict[str, List[str]]:
    return {"symbols": OTC_SYMBOLS}

# ----- Candle fetching -----
async def fetch_candles(symbol: str, interval: str, limit: int) -> Dict:
    """
    Returns a PO-shaped JSON:
    {
      "symbol": "...", "interval": "1m",
      "candles": [{"ts": 1700000000, "open":..., "high":..., "low":..., "close":..., "volume":0.0}, ...]
    }
    Strategy:
      1) If PO_UPSTREAM_URL is set -> call that (expects same response shape)
      2) Otherwise: raise a clear error telling the caller no upstream is set.
         (You can embed your local scraper here later.)
    """
    if PO_UPSTREAM_URL:
        url = f"{PO_UPSTREAM_URL}/candles"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, params=params)
            # Pass upstream errors through with context
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                detail = {"upstream_status": r.status_code, "upstream_text": r.text}
                raise HTTPException(status_code=502, detail=detail) from e
            try:
                data = r.json()
            except ValueError as e:
                raise HTTPException(status_code=502, detail="Upstream returned non-JSON") from e
        # basic shape check
        if "candles" not in data:
            raise HTTPException(status_code=502, detail="Upstream missing 'candles' field")
        return data

    # No upstream configured — tell the caller plainly.
    raise HTTPException(
        status_code=503,
        detail="No upstream configured. Set PO_UPSTREAM_URL to a service that returns PO-shaped candles."
    )