# Pocket Option OTC Candles Microservice

A tiny FastAPI service that logs into Pocket Option with Playwright and returns OTC candles via `/po/candles`.

> ⚠️ For personal use. Scraping may violate site ToS and may break if UI changes.

## Deploy (Render)

1. Create a new **Web Service** on https://render.com, **Build from repo** (use Docker).
2. Environment variables:
   - `PO_USER` – your Pocket Option email
   - `PO_PASS` – your Pocket Option password
   - `PO_SVC_TOKEN` – a long random string (shared secret with your bot)
3. After deploy, test:
   - `GET https://<your-service>/healthz` → `{"ok": true}`

## Endpoint

`GET /po/candles?symbol=EURUSD&interval=1m&limit=300`

Headers: `Authorization: Bearer <PO_SVC_TOKEN>`

Response (list of candles):
[{"t":1696273260,"o":1.06541,"h":1.06547,"l":1.06530,"c":1.06542}, ...]
