from __future__ import annotations
import os, httpx, asyncio
from datetime import datetime, timezone
from typing import List, Dict

TD_KEY = os.getenv("TWELVE_DATA_API_KEY", "")

def _map_symbol(symbol: str) -> str:
    # "EURUSD_OTC" -> "EUR/USD"
    s = symbol.replace("_OTC", "").replace("_", "").upper()
    return f"{s[:3]}/{s[3:]}"

def _map_interval(tf: str) -> str:
    tf = tf.lower()
    return {"1m": "1min", "5m": "5min", "15m": "15min"}.get(tf, "1min")

async def fetch_candles(symbol: str, interval: str, limit: int) -> List[Dict]:
    """
    Returns list of dicts with keys: ts, open, high, low, close, volume
    """
    if not TD_KEY:
        raise RuntimeError("Missing TWELVE_DATA_API_KEY")

    td_symbol = _map_symbol(symbol)
    td_interval = _map_interval(interval)
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": td_symbol,
        "interval": td_interval,
        "outputsize": max(limit, 500),
        "format": "JSON",
        "apikey": TD_KEY,
    }

    async with httpx.AsyncClient(timeout=25) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    vals = data.get("values")
    if not vals:
        return []

    # Twelve Data returns newest-first; normalize to oldest-first and limit
    rows = []
    for item in reversed(vals)[-limit:]:
        dt = datetime.fromisoformat(item["datetime"].replace("Z", "+00:00"))
        ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
        rows.append({
            "ts": ts,
            "open": float(item["open"]),
            "high": float(item["high"]),
            "low":  float(item["low"]),
            "close":float(item["close"]),
            "volume": float(item.get("volume", 0.0) or 0.0),
        })
    return rows