# scraper.py
import time
from typing import List, Dict

# NOTE: implement real Playwright flow here later. For now, return
# a deterministic-but-changing series so the pipeline is live.

async def fetch_candles(symbol: str, interval: str, limit: int) -> List[Dict]:
    """
    Must return: [{t,o,h,l,c}, ...] with UNIX seconds in 't'
    """
    # TODO: swap this mock with real Playwright:
    #  - launch chromium (headless per env)
    #  - log in with PO_USER/PO_PASS
    #  - navigate to the OTC chart for `symbol`
    #  - collect last `limit` candles
    #  - close browser and return candles

    # For now, vary a base price using time so values move each call.
    base = 1.071 + (int(time.time() // 60) % 9) * 0.00011
    now = int(time.time() // 60) * 60
    out = []
    for i in range(limit):
        t = now - 60 * (limit - 1 - i)
        o = round(base + (i % 5) * 0.00007, 6)
        h = round(o + 0.00015, 6)
        l = round(o - 0.00015, 6)
        c = round(o + ((-1) ** (i + 1)) * 0.00005, 6)
        out.append({"t": t, "o": o, "h": h, "l": l, "c": c})
    return out
