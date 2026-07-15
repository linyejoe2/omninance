"""
app.py — Omninance Backend FastAPI entry point.

Responsibilities:
  - Strategy CRUD (POST /api/strategies, GET /api/strategies, …)
  - Trade record history (GET /api/trade-records)
  - APScheduler: Mon-Fri 14:10 Asia/Taipei — triggers chip-tracker pipeline
    then executes all active strategies
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.db import init_db
from src.models import db as mongo_db
from src.routes.data_explorer import router as data_explorer_router
from src.routes.strategy import router as strategy_router
from src.scheduler import start_scheduler, stop_scheduler, router as scheduler_router
from src.core.logging_util import start_logging

logger = start_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await mongo_db.connect()
    start_scheduler()
    yield
    stop_scheduler()
    mongo_db.disconnect()


app = FastAPI(
    title="Omninance Backend",
    lifespan=lifespan,
    docs_url="/api-docs",
    redoc_url="/api-docs/redoc",
    openapi_url="/api-docs/openapi.json",
)

app.include_router(strategy_router)
app.include_router(scheduler_router)
app.include_router(data_explorer_router)


@app.get("/health")
def health():
    return {"status": "ok"}
