import os, httpx, asyncio

BASE = os.getenv("PUBLIC_BASE_URL", "").rstrip("/") or os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
TOKEN = os.getenv("PO_SVC_TOKEN", "")

async def candles(symbol="EURUSD_OTC", interval="1m", limit=5):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if TOKEN:
        params["token"] = TOKEN
    async with httpx.AsyncClient(timeout=25) as client:
        r = await client.get(f"{BASE}/api/candles", params=params)
        r.raise_for_status()
        return r.json()

if __name__ == "__main__":
    async def _t():
        print(await candles())
    asyncio.run(_t())