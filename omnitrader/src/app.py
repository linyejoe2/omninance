"""
app.py — OmniTrader FastAPI service entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.sdk_client import init_sdk, shutdown_sdk
from src.routes.orders import router as orders_router
from src.routes.account import router as account_router
from src.routes.signals import router as signals_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


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
app.include_router(signals_router)


@app.get("/health")
def health():
    return {"status": "ok"}
