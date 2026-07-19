"""Production entrypoint — Zoho Catalyst AppSail-aware.

AppSail injects the port to bind as ``X_ZOHO_CATALYST_LISTEN_PORT`` and terminates the
instance if the app hasn't bound it within 10 seconds — so the port must be read at runtime,
never hardcoded. Outside Catalyst (docker compose, bare dev box) it falls back to 8000.

Usage:
    python serve.py            # production / AppSail
    python serve.py --reload   # local dev with auto-reload (docker compose uses this)
"""

from __future__ import annotations

import os
import sys

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("X_ZOHO_CATALYST_LISTEN_PORT", "8000"))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload="--reload" in sys.argv[1:],
    )
