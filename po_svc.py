# po_svc_symbols.py
import os
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

router = APIRouter()

# ❶ Static list of OTC pairs the bot can watch (trim or expand any time).
ALL_OTC = [
    "EURUSD_OTC","GBPUSD_OTC","USDJPY_OTC","USDCHF_OTC","USDCAD_OTC","AUDUSD_OTC","NZDUSD_OTC",
    "EURJPY_OTC","EURGBP_OTC","EURAUD_OTC","EURNZD_OTC","EURCHF_OTC","EURCAD_OTC","GBPAUD_OTC",
    "GBPCAD_OTC","GBPJPY_OTC","GBPNZD_OTC","GBPCHF_OTC","AUDJPY_OTC","AUDCHF_OTC","AUDCAD_OTC",
    "AUDNZD_OTC","NZDJPY_OTC","NZDCHF_OTC","NZDCAD_OTC","CADJPY_OTC","CADCHF_OTC","CHFJPY_OTC",
    # regionals you showed with high payouts
    "USD/BDT_OTC","USD/VND_OTC","USD/INR_OTC","USD/IDR_OTC","USD/EGP_OTC","USD/THB_OTC","USD/MXN_OTC",
    "USD/PKR_OTC","USD/BRL_OTC","USD/UAH_OTC","USD/CNH_OTC","USD/SGD_OTC","ZAR/USD_OTC","QAR/CNY_OTC",
    "MAD/USD_OTC","TND/USD_OTC","BHD/CNY_OTC","OMR/CNY_OTC","KES/USD_OTC","NGN/USD_OTC",
    # add any others you want to support here
]

@router.get("/symbols")
def get_symbols(token: str = Query(..., description="service token")):
    svc_token = os.getenv("PO_SVC_TOKEN", "")
    if not svc_token or token != svc_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # Always 200 with a list; never 404
    return {"symbols": ALL_OTC}

# Optional: a very small helper to return an empty (but valid) envelope instead of 404
@router.get("/nodata")
def nodata():
    return JSONResponse({"candles": []}, status_code=200)