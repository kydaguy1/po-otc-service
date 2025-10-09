# po_svc.py
import os
import re
import time
from typing import Dict, Tuple, List
from scraper import get_candles_from_upstream

# === Auth ===
_SERVICE_TOKEN = os.getenv("PO_SVC_TOKEN", "").strip()

def verify_token(token: str):
    if not _SERVICE_TOKEN or token != _SERVICE_TOKEN:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthorized")

# === Symbol handling ===
# If you want to hard-limit, put a comma list in SYMBOLS_ALLOWLIST.
# If unset, we accept any <AAA><BBB>_OTC with letters only.
_ALLOWLIST = {s.strip().upper() for s in os.getenv("SYMBOLS_ALLOWLIST", "").split(",") if s.strip()}

_PAIR_RE = re.compile(r"^[A-Z]{3}[A-Z]{3}_OTC$")

def _valid_symbol(symbol: str) -> bool:
    s = symbol.upper()
    if _ALLOWLIST:
        return s in _ALLOWLIST
    return bool(_PAIR_RE.match(s))

# A curated list we expose via /symbols when there’s no explicit allowlist.
_DEFAULT_OTC_LIST: List[str] = [
    # major & common OTCs (expand freely)
    "EURUSD_OTC","GBPUSD_OTC","AUDUSD_OTC","USDJPY_OTC","USDCHF_OTC","USDCAD_OTC","NZDUSD_OTC",
    "EURGBP_OTC","EURAUD_OTC","EURJPY_OTC","EURCHF_OTC","EURCAD_OTC","EURNZD_OTC",
    "GBPAUD_OTC","GBPJPY_OTC","GBPCHF_OTC","GBPCAD_OTC","GBPNZD_OTC",
    "AUDJPY_OTC","AUDCHF_OTC","AUDCAD_OTC","AUDNZD_OTC",
    "CADJPY_OTC","CADCHF_OTC","NZDJPY_OTC","NZDCHF_OTC",
    # some exotics commonly seen in PO lists
    "USDTRY_OTC","USDRUB_OTC","USDBRL_OTC","USDZAR_OTC","USDMXN_OTC","USDINR_OTC","USDIDR_OTC",
    "USDPKR_OTC","USDSGD_OTC","USDTHB_OTC","USDEGP_OTC","USDCNH_OTC","USDCOP_OTC",
    "EURTRY_OTC","EURNOK_OTC","EURSEK_OTC","EURRUB_OTC","EURHUF_OTC",
    "GBPJPY_OTC","GBPAED_OTC","GBPRUB_OTC",
]

def list_symbols() -> List[str]:
    return sorted(_ALLOWLIST) if _ALLOWLIST else sorted(set(_DEFAULT_OTC_LIST))

# === Small in-memory cache to reduce scrape load ===
_CACHE: Dict[Tuple[str, str, int], Tuple[float, dict]] = {}
_TTL_S = int(os.getenv("CACHE_TTL_SECONDS", "2"))  # tiny cache, just to coalesce bursts

async def fetch_candles(symbol: str, interval: str, limit: int) -> dict:
    symbol = symbol.upper()

    if not _valid_symbol(symbol):
        raise ValueError(f"Unsupported symbol: {symbol}")

    if interval not in {"1m", "5m", "15m"}:
        raise ValueError("interval must be one of: 1m,5m,15m")

    key = (symbol, interval, min(limit, 240))
    now = time.time()
    hit = _CACHE.get(key)
    if hit and (now - hit[0]) < _TTL_S:
        return hit[1]

    data = await get_candles_from_upstream(symbol=symbol, interval=interval, limit=limit)

    # Normalize the response shape
    payload = {
        "symbol": symbol,
        "interval": interval,
        "candles": data["candles"] if isinstance(data, dict) and "candles" in data else data
    }

    _CACHE[key] = (now, payload)
    return payload