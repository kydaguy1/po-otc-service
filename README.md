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

## Env vars (Render/Replit Secrets)

- TELEGRAM_BOT_TOKEN = 12345:AAAA... (required)
- WEBHOOK_SECRET = amandaismywife (or your own)
- PUBLIC_BASE = https://<your-service>.onrender.com  (Render https URL)
- PO_SVC_URL = https://po-otc-ky.onrender.com
- PO_SVC_TOKEN = <if your service needs it; optional>
- OANDA_API_KEY = <optional; only if you use non-OTC symbols>

## Start (Render)
Start command: `python -m uvicorn main:app --host 0.0.0.0 --port 8080`

## Set the Telegram webhook (once per deploy)
Open:
`https://<PUBLIC_BASE>/admin/set_webhook?secret=<WEBHOOK_SECRET>`

## Telegram usage
- `/ping` → pong
- `watch EURUSD_OTC 1m strict=true`
- `watch GBPUSD_OTC 1m strict=false`
- `unwatch EURUSD_OTC 1m`
- `/watchers`

### Confidence emojis
- `✅` high (≥ 0.75)
- `🟡` medium (≥ 0.55 and < 0.75)
- `⚪️` low/none
