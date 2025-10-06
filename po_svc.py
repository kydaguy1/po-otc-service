import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List

app = FastAPI()
auth_scheme = HTTPBearer(auto_error=False)

PO_SVC_TOKEN = os.getenv("PO_SVC_TOKEN", "")
PO_MOCK = os.getenv("PO_MOCK", "true").lower() == "true"
PLAYWRIGHT_READY = os.getenv("PO_PLAYWRIGHT", "true").lower() == "true"

# import scraper only when needed so /healthz is always fast
def _import_scraper():
    from scraper import fetch_candles
    return fetch_candles

class Candle(BaseModel):
    t: int
    o: float
    h: float
    l: float
    c: float

def _auth(creds: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    if not PO_SVC_TOKEN:
        return  # unsecured
    if not creds or creds.scheme.lower() != "bearer" or creds.credentials != PO_SVC_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/")
def root():
    return {"ok": True}

@app.get("/healthz")
def healthz():
    return {"ok": True, "mock": PO_MOCK, "playwright": PLAYWRIGHT_READY}

@app.get("/po/candles", response_model=List[Candle], dependencies=[Depends(_auth)])
def po_candles(symbol: str, interval: str = "1m", limit: int = 3):
    """
    Example: /po/candles?symbol=EURUSD_OTC&interval=1m&limit=3
    """
    if PO_MOCK:
        # simple changing mock
        import time, random
        now = int(time.time()) // 60 * 60
        out = []
        price = 1.0710 + random.random() * 0.001
        for i in range(limit, 0, -1):
            t = now - i*60
            o = round(price, 6)
            h = round(o + 0.0002, 6)
            l = round(o - 0.0002, 6)
            c = round(o + (random.random()-0.5)*0.0003, 6)
            out.append({"t": t, "o": o, "h": h, "l": l, "c": c})
        return out

    # real scraper
    try:
        fetch_candles = _import_scraper()
    except Exception as e:
        raise HTTPException(status_code=501,
            detail=f"Real scraper not wired yet: {e}. Set PO_MOCK=true until scraper is implemented.")

    try:
        return fetch_candles(symbol=symbol, interval=interval, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"scraper error: {e}")