# po_svc.py
from typing import List, Dict, Any
import os, time, random

SUPPORTED = {
    "EURUSD_OTC", "GBPUSD_OTC", "USDJPY_OTC", "USDCHF_OTC", "USDCAD_OTC",
    "AUDUSD_OTC", "NZDUSD_OTC", "EURGBP_OTC", "EURJPY_OTC", "AUDJPY_OTC",
    "GBPJPY_OTC", "EURAUD_OTC", "EURCHF_OTC", "CADJPY_OTC", "AUDCAD_OTC",
    "AUDCHF_OTC", "GBPCAD_OTC", "NZDJPY_OTC", "NZDCHF_OTC", "CHFJPY_OTC"
}

def verify_token(token: str) -> bool:
    expected = os.getenv("PO_SVC_TOKEN", "")
    return bool(expected) and token == expected

def list_symbols() -> List[str]:
    return sorted(SUPPORTED)

def fetch_candles(symbol: str, interval: str, limit: int) -> Dict[str, Any]:
    if symbol not in SUPPORTED:
        return {"symbol": symbol, "interval": interval, "candles": []}

    now = int(time.time())
    step = 60 if interval == "1m" else 60
    candles, rnd = [], random.Random(hash(symbol) & 0xffffffff)
    price = 1.15500 + rnd.random() * 0.01

    for i in range(limit):
        ts = now - step * (limit - i)
        move = (rnd.random() - 0.5) * 0.0004
        o, c = price, max(0, price + move)
        h = max(o, c) + abs((rnd.random() - 0.5) * 0.0002)
        l = min(o, c) - abs((rnd.random() - 0.5) * 0.0002)
        candles.append({
            "ts": ts, "open": round(o, 5), "high": round(h, 5),
            "low": round(l, 5), "close": round(c, 5), "volume": 0.0
        })
        price = c
    return {"symbol": symbol, "interval": interval, "candles": candles}