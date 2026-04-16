"""
app.py — OmniTrader FastAPI service entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.sdk_client import init_sdk, shutdown_sdk
from src.routes.orders import router as orders_router
from src.routes.account import router as account_router
from src.core.logging_util import start_logging

logger = start_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_sdk()
    yield
    shutdown_sdk()


app = FastAPI(
    title="OmniTrader",
    lifespan=lifespan,
    docs_url="/api-docs",
    redoc_url="/api-docs/redoc",
    openapi_url="/api-docs/openapi.json",
)

app.include_router(orders_router)
app.include_router(account_router)


@app.get("/health")
def health():
    return {"status": "ok"}
