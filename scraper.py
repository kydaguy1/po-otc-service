"""
Stub scraper.

If you later want this Render service to scrape directly (not proxy to another
upstream), implement a function here that returns PO-shaped candles. Then call
it from po_svc.fetch_candles when PO_UPSTREAM_URL is not set.
"""
from typing import Dict, List

def example_stub() -> Dict[str, List[dict]]:
    # Example shape only
    return {
        "symbol": "EURUSD_OTC",
        "interval": "1m",
        "candles": []
    }