"""
app.py — Omninance Backend FastAPI entry point.

Responsibilities: strategy execution orchestration + SQLite history.
Signal/price-history/backtest are served directly by chip-tracker.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.db import init_db
from src.routes.strategy import router as strategy_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Omninance Backend",
    lifespan=lifespan,
    docs_url="/api-docs",
    redoc_url="/api-docs/redoc",
    openapi_url="/api-docs/openapi.json",
)

app.include_router(strategy_router)


@app.get("/health")
def health():
    return {"status": "ok"}
