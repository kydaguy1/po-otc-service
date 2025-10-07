# po_svc.py
import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run("po_api:app", host="0.0.0.0", port=port, reload=False)