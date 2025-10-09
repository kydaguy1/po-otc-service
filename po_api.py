from __future__ import annotations
import os, httpx
from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone

# ── Auth (query ?token=...) ─────────────────────────────────────
APP_TOKEN = os.getenv("PO_SVC_TOKEN", "")

def auth(token: Optional[str] = Query(default=None, alias="token")):
    if APP_TOKEN and token != APP_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# ── Temporary data source: Twelve Data (swap later to true PO) ─
TD_KEY = os.getenv("TWELVE_DATA_API_KEY", "")

def td_symbol(symbol: str) -> str:
    s = symbol.replace("_OTC", "").replace("_", "").upper()
    return f"{s[:3]}/{s[3:]}"

def td_interval(tf: str) -> str:
    return {"1m": "1min", "5m": "5min", "15m": "15min"}.get(tf.lower(), "1min")

async def fetch_candles(symbol: str, interval: str, limit: int):
    if not TD_KEY:
        raise RuntimeError("Missing TWELVE_DATA_API_KEY")
    params = {
        "symbol": td_symbol(symbol),
        "interval": td_interval(interval),
        "outputsize": max(500, limit),
        "format": "JSON",
        "apikey": TD_KEY,
    }
    async with httpx.AsyncClient(timeout=25) as client:
        r = await client.get("https://api.twelvedata.com/time_series", params=params)
        r.raise_for_status()
        data = r.json()

    vals = data.get("values") or []
    rows: List[dict] = []
    # FIX: convert reversed iterator to list before slicing
    for item in list(reversed(vals))[-limit:]:
        dt = datetime.fromisoformat(item["datetime"].replace("Z", "+00:00")).astimezone(timezone.utc)
        rows.append({
            "ts": int(dt.timestamp()),
            "open": float(item["open"]),
            "high": float(item["high"]),
            "low":  float(item["low"]),
            "close": float(item["close"]),
            "volume": float(item.get("volume") or 0.0),
        })
    return rows

# ── API ─────────────────────────────────────────────────────────
app = FastAPI(title="PO OTC Candles API", version="1.0.0")

class Candle(BaseModel):
    ts: int; open: float; high: float; low: float; close: float; volume: float = 0.0

class CandlesResponse(BaseModel):
    symbol: str; interval: str; candles: List[Candle]

@app.get("/health")
def health(): return {"ok": True}

@app.get("/api/candles", response_model=CandlesResponse)
async def api_candles(symbol: str, interval: str = "1m", limit: int = 200, _=Depends(auth)):
    try:
        rows = await fetch_candles(symbol, interval, limit)
        if not rows:
            raise HTTPException(status_code=404, detail="No data")
        return {"symbol": symbol, "interval": interval, "candles": rows}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))