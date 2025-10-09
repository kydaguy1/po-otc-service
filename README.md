# PO OTC Candles API

## Endpoints
- `GET /health`
- `GET /api/candles?symbol=EURUSD_OTC&interval=1m&limit=200[&token=XYZ]`

## Env Vars
- `TWELVE_DATA_API_KEY` (required for now)
- `PO_SVC_TOKEN` (optional; if set, requests must include `?token=...`)

## Local run