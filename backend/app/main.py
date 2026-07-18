"""FastAPI entrypoint.

P1 provides health checks only. The chat endpoint and tool registry land in P14.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import check_connection

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="KSP Crime Intelligence Platform",
    description="Conversational AI and crime analytics over the Karnataka State Police FIR database",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
def health_db() -> dict[str, object]:
    """Confirms the database is reachable and both schemas were created."""
    try:
        return {"status": "ok", **check_connection()}
    except Exception as exc:  # surfaced deliberately — this is a dev-time probe
        return {"status": "error", "detail": str(exc)}
