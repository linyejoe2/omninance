"""
app.py — Omninance Backend FastAPI entry point.

Responsibilities:
  - Strategy CRUD + positions / order-records / daily-logs read APIs
    (PostgreSQL via SQLModel, schema managed by alembic)
  - Strategy trading jobs and data refreshes, all triggered by the
    ofelia scheduler container on a cron schedule (see /ofelia.ini)
  - Read-only data explorer over the MongoDB stock collections
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.db import init_db
from src.models import db as mongo_db
from src.routes.data_explorer import router as data_explorer_router
from src.routes.holder import router as holder_router
from src.routes.schedule import router as schedule_router
from src.routes.stock_list import router as stock_list_router
from src.routes.ticker import router as ticker_router
from src.routes.strategy import router as strategy_router
from src.core.logging_util import start_logging

logger = start_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await mongo_db.connect()
    yield
    mongo_db.disconnect()


app = FastAPI(
    title="Omninance Backend",
    lifespan=lifespan,
    docs_url="/api-docs",
    redoc_url="/api-docs/redoc",
    openapi_url="/api-docs/openapi.json",
)

app.include_router(strategy_router)
app.include_router(data_explorer_router)
app.include_router(stock_list_router)
app.include_router(holder_router)
app.include_router(schedule_router)
app.include_router(ticker_router)


@app.get("/health")
def health():
    return {"status": "ok"}
