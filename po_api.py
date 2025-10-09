from __future__ import annotations
import os
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from scraper import fetch_candles  # <- pluggable source (Twelve Data now; PO later)

APP_TOKEN = os.getenv("PO_SVC_TOKEN", "")

app = FastAPI(title="PO OTC Candles API", version="1.0.0")

# --- simple bearer check (optional but supported by your bot) ---
def auth(token: Optional[str] = Query(default=None, alias="token")):
    if APP_TOKEN and token != APP_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

class Candle(BaseModel):
    ts: int    # epoch seconds
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

class CandlesResponse(BaseModel):
    symbol: str
    interval: str
    candles: List[Candle]

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/candles", response_model=CandlesResponse)
async def api_candles(
    symbol: str,
    interval: str = "1m",
    limit: int = 200,
    _=Depends(auth)
):
    """
    Returns OHLCV candles in a stable JSON shape:
    {
      "symbol": "EURUSD_OTC",
      "interval": "1m",
      "candles": [{"ts":..., "open":..., "high":..., "low":..., "close":..., "volume":...}, ...]
    }
    """
    try:
        rows = await fetch_candles(symbol=symbol, interval=interval, limit=limit)
        if not rows:
            raise HTTPException(status_code=404, detail="No data")
        return {"symbol": symbol, "interval": interval, "candles": rows}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))