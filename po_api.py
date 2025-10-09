# po_api.py
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
from po_svc import verify_token, list_symbols, fetch_candles

app = FastAPI(title="PO OTC Service", version="1.2.0")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/symbols")
def symbols(token: str = Query(..., description="service token")):
    verify_token(token)
    return {"symbols": list_symbols()}

@app.get("/candles")
async def candles(
    symbol: str = Query(..., description="e.g. EURUSD_OTC"),
    interval: str = Query("1m", description="1m|5m|15m"),
    limit: int = Query(200, ge=1, le=240),
    token: str = Query(...)
):
    verify_token(token)

    try:
        data = await fetch_candles(symbol=symbol, interval=interval, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        # Upstream has no data for this symbol right now
        raise HTTPException(status_code=404, detail="No data")
    except Exception as e:
        # Don’t leak internals
        raise HTTPException(status_code=500, detail=str(e))

    if not data or not data.get("candles"):
        # normalize empty -> 404 so callers can backoff
        raise HTTPException(status_code=404, detail="No data")

    return JSONResponse(data)