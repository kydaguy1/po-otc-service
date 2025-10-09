"""
FastAPI app exposing:
  GET /health
  GET /symbols?token=...
  GET /candles?symbol=...&interval=1m&limit=200&token=...

Auth:
  All endpoints except /health require a 'token' query param
  that matches PO_SVC_TOKEN (env in Render).

Upstream:
  If PO_UPSTREAM_URL is set in the environment, po_svc.fetch_candles will
  proxy there. Otherwise it returns 503 telling you to configure it.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI, Query
from fastapi.responses import JSONResponse

from po_svc import verify_token, list_symbols, fetch_candles

app = FastAPI(title="PO OTC Service", version="1.0.0")

# ----- Dependencies -----
def auth(token: Optional[str] = Query(None)) -> None:
    verify_token(token)

# ----- Routes -----
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/symbols")
def symbols(_: None = Depends(auth)):
    return list_symbols()

@app.get("/candles")
async def candles(
    symbol: str = Query(..., description="e.g. EURUSD_OTC"),
    interval: str = Query("1m"),
    limit: int = Query(200, ge=1, le=1200),
    _: None = Depends(auth),
):
    data = await fetch_candles(symbol, interval, limit)
    return JSONResponse(content=data)