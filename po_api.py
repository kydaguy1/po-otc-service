# po_api.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
from po_svc import verify_token, list_symbols, fetch_candles

app = FastAPI(title="PO OTC Datafeed", version="1.0")

@app.get("/health")
def health():
    return {"ok": True}

def _check_token(token: Optional[str]):
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/symbols")
def symbols(token: str = Query(...)):
    _check_token(token)
    return {"symbols": list_symbols()}

@app.get("/candles")
def candles(symbol: str, interval: str = "1m", limit: int = 200, token: str = Query(...)):
    _check_token(token)
    data = fetch_candles(symbol, interval, limit)
    if not data.get("candles"):
        raise HTTPException(status_code=404, detail="No data")
    return JSONResponse(data)