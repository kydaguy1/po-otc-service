import os, time, random
from fastapi import FastAPI, Query, Header, HTTPException

app = FastAPI()

TOKEN = os.environ.get("PO_SVC_TOKEN", "")
MOCK  = os.environ.get("PO_MOCK", "true").lower() == "true"

def _auth(auth: str | None):
    if TOKEN and (auth or "") != f"Bearer {TOKEN}":
        raise HTTPException(401, "Unauthorized")

@app.get("/")
async def root():  # Render’s default probe might hit /
    return {"ok": True}

@app.get("/healthz")
async def healthz():
    return {"ok": True, "mock": MOCK, "playwright": False}

@app.get("/po/candles")
async def po_candles(
    symbol: str = Query(...),
    interval: str = Query("1m"),
    limit: int = Query(3, ge=1, le=500),
    authorization: str | None = Header(None, convert_underscores=False),
):
    _auth(authorization)
    # MOCK: produce moving value so Telegram isn’t stuck on one price
    base = 1.07200
    now  = int(time.time())
    step = 60 if interval.endswith("m") else 1
    out = []
    price = base + random.uniform(-0.001, 0.001)
    for i in range(limit):
        t = now - (limit - 1 - i) * step
        # small jitter so each minute changes
        jitter = random.uniform(-0.0002, 0.0002)
        o = round(price + jitter*0.2, 6)
        h = round(o + abs(jitter), 6)
        l = round(o - abs(jitter), 6)
        c = round(o + jitter*0.3, 6)
        out.append({"t": t, "o": o, "h": h, "l": l, "c": c})
        price = c
    return out
