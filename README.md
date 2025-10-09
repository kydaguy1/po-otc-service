# PO OTC Service (Render)

A tiny FastAPI proxy that returns PocketOption-style OTC candles for your bot.

## Endpoints

- `GET /health` → `{ "ok": true }`
- `GET /symbols?token=...` → `{ "symbols": ["EURUSD_OTC", ...] }`
- `GET /candles?symbol=EURUSD_OTC&interval=1m&limit=200&token=...`
  → 
  ```json
  {
    "symbol": "EURUSD_OTC",
    "interval": "1m",
    "candles": [
      {"ts": 1760000000, "open": 1.1, "high": 1.12, "low": 1.09, "close": 1.11, "volume": 0.0}
    ]
  }