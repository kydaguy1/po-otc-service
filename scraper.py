# scraper.py
"""
Single place that pulls OTC candles from the upstream source used for EURUSD_OTC,
now generalized for ANY <AAABBB>_OTC.

We keep it async + httpx so it runs fine on Render without a browser.
If your current working upstream code for EURUSD_OTC used a different client,
just plug it inside `_fetch_raw_candles` and keep the function signature.
"""
import os
import asyncio
import httpx
from typing import Dict, Any, List

# Upstream the service already uses (whatever produced valid EURUSD_OTC for you).
# If you were scraping a websocket originally, point to your internal aggregator here.
PO_BASE_URL = os.getenv("PO_BASE_URL", "").rstrip("/")  # keep optional, not required
# Fallback: use the same server instance that serves this code (self-scrape protection off)
# but in practice you should point to the actual data source you used for EURUSD_OTC.

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))

def _to_tv_symbol(symbol: str) -> str:
    # If your upstream expects another format, adapt here.
    # PocketOption/TV mappings often accept the same token (EURUSD_OTC).
    return symbol

async def _fetch_raw_candles(symbol: str, interval: str, limit: int) -> List[Dict[str, Any]]:
    """
    Replace this with the exact request you already had for EURUSD_OTC.
    The only change you need is to pass-through `symbol` instead of hard-coding it.
    This example assumes you had an HTTP JSON endpoint that returns:
       [{"ts": 1712345678, "open":..., "high":..., "low":..., "close":..., "volume":0.0}, ...]
    """
    # >>> START: Example using a generic upstream you already wired for EURUSD_OTC <<<
    # If you had a direct upstream URL, set it in env PO_UPSTREAM_URL like:
    #   https://your-existing-upstream.example.com/po/candles
    PO_UPSTREAM_URL = os.getenv("PO_UPSTREAM_URL", "").rstrip("/")
    if not PO_UPSTREAM_URL:
        # If you didn't set a separate upstream, we raise — configuring it is required
        # for symbols beyond EURUSD_OTC.
        raise FileNotFoundError("No upstream configured for OTC candles (set PO_UPSTREAM_URL)")
    params = {
        "symbol": _to_tv_symbol(symbol),
        "interval": interval,
        "limit": min(limit, 240)
    }
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        r = await client.get(PO_UPSTREAM_URL, params=params)
        if r.status_code == 404:
            raise FileNotFoundError("Upstream has no data")
        r.raise_for_status()
        candles = r.json()
    # <<< END example >>>
    return candles

def _normalize(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for c in candles:
        # accept either {"ts":...} or {"time":...}
        ts = c.get("ts") or c.get("time") or c.get("timestamp")
        if ts is None:
            continue
        out.append({
            "ts": int(ts),
            "open": float(c.get("open", 0.0)),
            "high": float(c.get("high", c.get("open", 0.0))),
            "low": float(c.get("low", c.get("open", 0.0))),
            "close": float(c.get("close", c.get("open", 0.0))),
            "volume": float(c.get("volume", 0.0)),
        })
    return out[-240:]  # hard cap

async def get_candles_from_upstream(symbol: str, interval: str, limit: int):
    raw = await _fetch_raw_candles(symbol=symbol, interval=interval, limit=limit)
    return {"candles": _normalize(raw)[-limit:]}