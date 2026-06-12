# main.py — northstar-bank
# FastAPI application entrypoint.
# Mounts all routers and manages connection pool lifecycle.

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat_router import router as chat_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BankIQ — Smart Banking Assistant",
    description="Agentic RAG + NL-to-SQL API for BFSI",
    version="0.1.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow Streamlit UI (localhost:8501) to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(chat_router, tags=["Chat"])


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
